"""Tests for insight-ledger. All rule-based; LLM tested via mocks."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from insight_ledger.engine import (
    Ledger,
    compute_summary,
    filter_records,
    insight_influence_score,
    ranked_insights,
    resolve_proposals,
    resolve_records,
)
from insight_ledger.models import (
    Decision,
    DecisionType,
    Insight,
    InsightLink,
    LedgerRecord,
    LinkStatus,
    LinkStrength,
)
from insight_ledger.synthetic import load_synthetic_ledger


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def ins_a():
    return Insight(id="i001", title="Nav confusion", summary="Users lost in onboarding.",
                   study_name="Q1 Usability", study_date="2026-01-15", researcher="Alice",
                   tags=["navigation", "onboarding"], raw_evidence="'Can't find projects.'",
                   confidence=0.9)


@pytest.fixture
def ins_b():
    return Insight(id="i002", title="Notification fatigue", summary="High volume caused abandonment.",
                   study_name="Diary Study", study_date="2026-02-01",
                   researcher="Bob", tags=["notifications"], confidence=0.8)


@pytest.fixture
def dec_a():
    return Decision(id="d001", title="Add sidebar nav", description="Fixed sidebar for Projects.",
                    decision_type=DecisionType.DESIGN.value, decision_date="2026-02-01",
                    owner="Priya", team="Growth", reference="design-brief-feb-2026")


@pytest.fixture
def dec_b():
    return Decision(id="d002", title="Digest mode", description="Bundle notifications.",
                    decision_type=DecisionType.FEATURE.value, decision_date="2026-03-01",
                    owner="Marcus", team="Platform", reference="feature-spec-digest")


@pytest.fixture
def link_confirmed(ins_a, dec_a):
    return InsightLink(id="l001", insight_id="i001", decision_id="d001",
                       status=LinkStatus.ADOPTED.value, strength=LinkStrength.HIGH.value,
                       rationale="Direct cause.", logged_by="Alice", logged_date="2026-02-02")


@pytest.fixture
def link_partial(ins_b, dec_b):
    return InsightLink(id="l002", insight_id="i002", decision_id="d002",
                       status=LinkStatus.PARTIAL.value, strength=LinkStrength.MEDIUM.value,
                       rationale="Partially adopted.", logged_by="Bob", logged_date="2026-03-05")


@pytest.fixture
def link_proposed(ins_b, dec_a):
    return InsightLink(id="p001", insight_id="i002", decision_id="d001",
                       status=LinkStatus.PROPOSED.value, strength=LinkStrength.MEDIUM.value,
                       rationale="LLM proposed rationale.", auto_proposed=True,
                       proposal_confidence=0.72, logged_date="2026-04-01")


@pytest.fixture
def ledger(ins_a, ins_b, dec_a, dec_b, link_confirmed, link_partial, link_proposed):
    ldr = Ledger()
    ldr.add_insight(ins_a)
    ldr.add_insight(ins_b)
    ldr.add_decision(dec_a)
    ldr.add_decision(dec_b)
    ldr.add_link(link_confirmed)
    ldr.add_link(link_partial)
    ldr.add_link(link_proposed)
    return ldr


# ── Model tests ───────────────────────────────────────────────────────────────

class TestModels:
    def test_insight_defaults(self):
        ins = Insight()
        assert ins.id and ins.tags == [] and ins.confidence == 0.8

    def test_decision_reference_default(self):
        dec = Decision()
        assert dec.reference == ""

    def test_link_defaults(self):
        lk = InsightLink()
        assert lk.auto_proposed is False
        assert lk.proposal_confidence == 0.0
        assert lk.llm_note is None

    def test_link_proposed_fields(self, link_proposed):
        assert link_proposed.auto_proposed is True
        assert link_proposed.proposal_confidence == 0.72
        assert link_proposed.status == "proposed"

    def test_link_to_dict_includes_new_fields(self, link_proposed):
        d = link_proposed.to_dict()
        assert "auto_proposed" in d
        assert "proposal_confidence" in d
        assert d["auto_proposed"] is True

    def test_record_is_proposed(self, ins_b, dec_a, link_proposed):
        r = LedgerRecord(link=link_proposed, insight=ins_b, decision=dec_a)
        assert r.is_proposed is True

    def test_record_not_proposed_for_confirmed(self, ins_a, dec_a, link_confirmed):
        r = LedgerRecord(link=link_confirmed, insight=ins_a, decision=dec_a)
        assert r.is_proposed is False

    def test_link_status_enum_has_proposed(self):
        assert LinkStatus.PROPOSED.value == "proposed"


# ── Ledger store tests ────────────────────────────────────────────────────────

class TestLedgerStore:
    def test_list_proposed(self, ledger):
        proposed = ledger.list_proposed()
        assert len(proposed) == 1
        assert proposed[0].id == "p001"

    def test_list_confirmed(self, ledger):
        confirmed = ledger.list_confirmed()
        assert len(confirmed) == 2
        assert all(lk.status != "proposed" for lk in confirmed)

    def test_existing_pairs(self, ledger):
        pairs = ledger.existing_pairs()
        assert ("i001", "d001") in pairs
        assert ("i002", "d001") in pairs  # proposed pair also included

    def test_persistence_roundtrip(self, ins_a, dec_a, link_confirmed, link_proposed):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        ldr = Ledger(store_path=path)
        ldr.add_insight(ins_a)
        ldr.add_decision(dec_a)
        ldr.add_link(link_confirmed)
        ldr.add_link(link_proposed)
        ldr2 = Ledger(store_path=path)
        assert ldr2.get_link("l001").status == "adopted"
        assert ldr2.get_link("p001").auto_proposed is True
        assert ldr2.get_link("p001").proposal_confidence == 0.72
        Path(path).unlink(missing_ok=True)

    def test_persistence_empty_file(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        ldr = Ledger(store_path=path)
        assert len(ldr.list_insights()) == 0
        Path(path).unlink(missing_ok=True)

    def test_delete_link(self, ledger):
        assert ledger.delete_link("p001") is True
        assert ledger.get_link("p001") is None


# ── Engine tests ──────────────────────────────────────────────────────────────

class TestEngine:
    def test_resolve_records_excludes_proposed_by_default(self, ledger):
        records = resolve_records(ledger)
        assert len(records) == 2
        assert all(r.link.status != "proposed" for r in records)

    def test_resolve_records_includes_proposed_when_flagged(self, ledger):
        records = resolve_records(ledger, include_proposed=True)
        assert len(records) == 3

    def test_resolve_proposals(self, ledger):
        proposals = resolve_proposals(ledger)
        assert len(proposals) == 1
        assert proposals[0].link.id == "p001"
        assert proposals[0].is_proposed is True

    def test_resolve_proposals_sorted_by_confidence(self):
        ldr = Ledger()
        ins_a = Insight(id="i001", title="A", confidence=0.9)
        dec_a = Decision(id="d001", title="X")
        dec_b = Decision(id="d002", title="Y")
        ldr.insights["i001"] = ins_a
        ldr.decisions["d001"] = dec_a
        ldr.decisions["d002"] = dec_b
        ldr.links["p001"] = InsightLink(id="p001", insight_id="i001", decision_id="d001",
                                         status="proposed", auto_proposed=True, proposal_confidence=0.6)
        ldr.links["p002"] = InsightLink(id="p002", insight_id="i001", decision_id="d002",
                                         status="proposed", auto_proposed=True, proposal_confidence=0.9)
        proposals = resolve_proposals(ldr)
        assert proposals[0].link.proposal_confidence > proposals[1].link.proposal_confidence

    def test_compute_summary_proposed_excluded_from_total_links(self, ledger):
        records = resolve_records(ledger)
        s = compute_summary(ledger, records)
        assert s.total_links == 2  # proposed excluded

    def test_compute_summary_proposed_count_correct(self, ledger):
        records = resolve_records(ledger)
        s = compute_summary(ledger, records)
        assert s.proposed_count == 1

    def test_activation_rate_excludes_proposed(self, ledger):
        records = resolve_records(ledger)
        s = compute_summary(ledger, records)
        # 1 adopted, 1 partial → (1 + 0.5) / 2 = 0.75
        assert s.activation_rate == pytest.approx(0.75, rel=0.01)

    def test_filter_by_status(self, ledger):
        records = resolve_records(ledger)
        adopted = filter_records(records, status="adopted")
        assert len(adopted) == 1

    def test_influence_score_excludes_proposed(self, ins_b, ledger):
        records = resolve_records(ledger, include_proposed=True)
        score = insight_influence_score(ins_b, records)
        # only partial/medium link counts, proposed excluded
        # 0.6 * 0.5 * 0.8 = 0.24
        assert score == pytest.approx(0.24, rel=0.01)

    def test_ranked_excludes_proposed(self, ledger):
        results = ranked_insights(ledger)
        assert len(results) == 2
        scores = [score for _, score in results]
        assert scores[0] >= scores[1]

    def test_empty_ledger(self):
        ldr = Ledger()
        s = compute_summary(ldr, [])
        assert s.total_links == 0
        assert s.proposed_count == 0
        assert s.activation_rate == 0.0


# ── Synthetic tests ───────────────────────────────────────────────────────────

class TestSynthetic:
    def test_counts(self):
        ldr = load_synthetic_ledger()
        assert len(ldr.list_insights()) == 6
        assert len(ldr.list_decisions()) == 6
        assert len(ldr.list_links()) == 10  # 7 confirmed + 3 proposed

    def test_confirmed_and_proposed_split(self):
        ldr = load_synthetic_ledger()
        assert len(ldr.list_confirmed()) == 7
        assert len(ldr.list_proposed()) == 3

    def test_summary_excludes_proposed(self):
        ldr = load_synthetic_ledger()
        records = resolve_records(ldr)
        s = compute_summary(ldr, records)
        assert s.total_links == 7
        assert s.proposed_count == 3

    def test_proposals_sorted_by_confidence(self):
        ldr = load_synthetic_ledger()
        proposals = resolve_proposals(ldr)
        confs = [p.link.proposal_confidence for p in proposals]
        assert confs == sorted(confs, reverse=True)

    def test_reference_field_no_atlassian(self):
        ldr = load_synthetic_ledger()
        for dec in ldr.list_decisions():
            ref = dec.reference.lower()
            assert "jira" not in ref
            assert "atlassian" not in ref
            assert "confluence" not in ref

    def test_no_atlassian_in_rationales(self):
        ldr = load_synthetic_ledger()
        for lk in ldr.list_links():
            assert "atlassian" not in (lk.rationale or "").lower()
            assert "jira" not in (lk.rationale or "").lower()

    def test_export_json_roundtrip(self):
        ldr = load_synthetic_ledger()
        data = ldr.export_json()
        parsed = json.loads(json.dumps(data))
        assert len(parsed["links"]) == 10
        proposed = [lk for lk in parsed["links"] if lk["status"] == "proposed"]
        assert len(proposed) == 3
        for p in proposed:
            assert p["auto_proposed"] is True
            assert p["proposal_confidence"] > 0


# ── LLM mock tests ────────────────────────────────────────────────────────────

class TestLLMMocked:
    def test_generate_link_note(self, ins_a, dec_a, link_confirmed):
        from insight_ledger import llm
        with patch.object(llm, "_detect_backend", return_value="anthropic/claude-opus-4-7"), \
             patch.object(llm, "_call_llm", return_value="Navigation confusion drove the sidebar spec."):
            result = llm.generate_link_note(ins_a, dec_a, link_confirmed)
            assert isinstance(result, str) and len(result) > 5

    def test_generate_link_note_no_backend(self, ins_a, dec_a, link_confirmed):
        from insight_ledger import llm
        with patch.object(llm, "_detect_backend", return_value=None):
            assert llm.generate_link_note(ins_a, dec_a, link_confirmed) is None

    def test_generate_narrative(self, ledger):
        from insight_ledger import llm
        records = resolve_records(ledger)
        s = compute_summary(ledger, records)
        with patch.object(llm, "_detect_backend", return_value="openai/gpt-5.5"), \
             patch.object(llm, "_call_llm", return_value="Research drove 2 decisions, 75% activation."):
            result = llm.generate_ledger_narrative(s, records)
            assert isinstance(result, str)

    def test_propose_links_returns_proposed_status(self, ledger):
        from insight_ledger import llm
        mock_json = json.dumps([
            {"insight_id": "i001", "decision_id": "d002", "confidence": 0.75,
             "rationale": "Navigation confusion relates to digest feature discoverability."}
        ])
        with patch.object(llm, "_detect_backend", return_value="anthropic/claude-opus-4-7"), \
             patch.object(llm, "_call_llm", return_value=mock_json):
            results = llm.propose_links(ledger, top_k=3, threshold=0.5)
            assert len(results) == 1
            assert results[0].status == "proposed"
            assert results[0].auto_proposed is True
            assert results[0].proposal_confidence == pytest.approx(0.75, rel=0.01)

    def test_propose_links_skips_existing_pairs(self, ledger):
        from insight_ledger import llm
        # i001→d001 already exists — should be skipped
        mock_json = json.dumps([
            {"insight_id": "i001", "decision_id": "d001", "confidence": 0.9,
             "rationale": "Already linked — should be filtered."}
        ])
        with patch.object(llm, "_detect_backend", return_value="anthropic/claude-opus-4-7"), \
             patch.object(llm, "_call_llm", return_value=mock_json):
            results = llm.propose_links(ledger, top_k=3, threshold=0.5)
            assert len(results) == 0

    def test_propose_links_respects_threshold(self, ledger):
        from insight_ledger import llm
        mock_json = json.dumps([
            {"insight_id": "i001", "decision_id": "d002", "confidence": 0.3,
             "rationale": "Weak link, below threshold."}
        ])
        with patch.object(llm, "_detect_backend", return_value="anthropic/claude-opus-4-7"), \
             patch.object(llm, "_call_llm", return_value=mock_json):
            results = llm.propose_links(ledger, top_k=3, threshold=0.5)
            assert len(results) == 0

    def test_propose_links_no_backend(self, ledger):
        from insight_ledger import llm
        with patch.object(llm, "_detect_backend", return_value=None):
            results = llm.propose_links(ledger)
            assert results == []

    def test_propose_links_invalid_json_returns_empty(self, ledger):
        from insight_ledger import llm
        with patch.object(llm, "_detect_backend", return_value="anthropic/claude-opus-4-7"), \
             patch.object(llm, "_call_llm", return_value="not valid json at all"):
            results = llm.propose_links(ledger)
            assert results == []

    def test_available_backends_no_keys(self):
        from insight_ledger import llm
        with patch.dict("os.environ", {}, clear=True):
            assert isinstance(llm.available_backends(), list)
