"""
Core engine for insight-ledger.

Rule-based: no API key required.
Operates on in-memory or JSON-persisted stores.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Optional

from .models import (
    Decision,
    Insight,
    InsightLink,
    LedgerRecord,
    LedgerSummary,
    LinkStatus,
    LinkStrength,
)


class Ledger:
    """In-memory store, optionally persisted to a JSON file."""

    def __init__(self, store_path: Optional[str] = None) -> None:
        self.store_path = Path(store_path) if store_path else None
        self.insights: dict[str, Insight] = {}
        self.decisions: dict[str, Decision] = {}
        self.links: dict[str, InsightLink] = {}
        if self.store_path and self.store_path.exists():
            self._load()

    # ── Insights ──────────────────────────────────────────────────────────────

    def add_insight(self, insight: Insight) -> Insight:
        self.insights[insight.id] = insight
        self._save()
        return insight

    def get_insight(self, insight_id: str) -> Optional[Insight]:
        return self.insights.get(insight_id)

    def list_insights(self) -> list[Insight]:
        return list(self.insights.values())

    def update_insight(self, insight: Insight) -> Insight:
        self.insights[insight.id] = insight
        self._save()
        return insight

    def delete_insight(self, insight_id: str) -> bool:
        if insight_id in self.insights:
            del self.insights[insight_id]
            self._save()
            return True
        return False

    # ── Decisions ─────────────────────────────────────────────────────────────

    def add_decision(self, decision: Decision) -> Decision:
        self.decisions[decision.id] = decision
        self._save()
        return decision

    def get_decision(self, decision_id: str) -> Optional[Decision]:
        return self.decisions.get(decision_id)

    def list_decisions(self) -> list[Decision]:
        return list(self.decisions.values())

    def update_decision(self, decision: Decision) -> Decision:
        self.decisions[decision.id] = decision
        self._save()
        return decision

    def delete_decision(self, decision_id: str) -> bool:
        if decision_id in self.decisions:
            del self.decisions[decision_id]
            self._save()
            return True
        return False

    # ── Links ─────────────────────────────────────────────────────────────────

    def add_link(self, link: InsightLink) -> InsightLink:
        self.links[link.id] = link
        self._save()
        return link

    def get_link(self, link_id: str) -> Optional[InsightLink]:
        return self.links.get(link_id)

    def list_links(self) -> list[InsightLink]:
        return list(self.links.values())

    def list_proposed(self) -> list[InsightLink]:
        return [lk for lk in self.links.values() if lk.status == LinkStatus.PROPOSED.value]

    def list_confirmed(self) -> list[InsightLink]:
        return [lk for lk in self.links.values() if lk.status != LinkStatus.PROPOSED.value]

    def links_for_insight(self, insight_id: str) -> list[InsightLink]:
        return [lk for lk in self.links.values() if lk.insight_id == insight_id]

    def links_for_decision(self, decision_id: str) -> list[InsightLink]:
        return [lk for lk in self.links.values() if lk.decision_id == decision_id]

    def existing_pairs(self) -> set[tuple[str, str]]:
        """Return the set of (insight_id, decision_id) pairs that already have any link."""
        return {(lk.insight_id, lk.decision_id) for lk in self.links.values()}

    def delete_link(self, link_id: str) -> bool:
        if link_id in self.links:
            del self.links[link_id]
            self._save()
            return True
        return False

    # ── Persistence ───────────────────────────────────────────────────────────

    def _save(self) -> None:
        if not self.store_path:
            return
        data = {
            "insights": {k: v.to_dict() for k, v in self.insights.items()},
            "decisions": {k: v.to_dict() for k, v in self.decisions.items()},
            "links": {k: v.to_dict() for k, v in self.links.items()},
        }
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        self.store_path.write_text(json.dumps(data, indent=2))

    def _load(self) -> None:
        text = self.store_path.read_text().strip()
        if not text:
            return
        data = json.loads(text)
        self.insights = {k: Insight(**v) for k, v in data.get("insights", {}).items()}
        self.decisions = {k: Decision(**v) for k, v in data.get("decisions", {}).items()}
        self.links = {k: InsightLink(**v) for k, v in data.get("links", {}).items()}

    def export_json(self) -> dict:
        return {
            "insights": [v.to_dict() for v in self.insights.values()],
            "decisions": [v.to_dict() for v in self.decisions.values()],
            "links": [v.to_dict() for v in self.links.values()],
        }


# ── Query helpers ──────────────────────────────────────────────────────────────

def resolve_records(ledger: Ledger, include_proposed: bool = False) -> list[LedgerRecord]:
    """
    Join links with their insight and decision.
    By default excludes proposed links (they are unconfirmed).
    """
    records = []
    for link in ledger.list_links():
        if not include_proposed and link.status == LinkStatus.PROPOSED.value:
            continue
        insight = ledger.get_insight(link.insight_id)
        decision = ledger.get_decision(link.decision_id)
        if insight and decision:
            records.append(LedgerRecord(link=link, insight=insight, decision=decision))
    return records


def resolve_proposals(ledger: Ledger) -> list[LedgerRecord]:
    """Return only proposed (unconfirmed) records."""
    records = []
    for link in ledger.list_proposed():
        insight = ledger.get_insight(link.insight_id)
        decision = ledger.get_decision(link.decision_id)
        if insight and decision:
            records.append(LedgerRecord(link=link, insight=insight, decision=decision))
    return sorted(records, key=lambda r: r.link.proposal_confidence, reverse=True)


def filter_records(
    records: list[LedgerRecord],
    status: Optional[str] = None,
    strength: Optional[str] = None,
    researcher: Optional[str] = None,
    team: Optional[str] = None,
    tag: Optional[str] = None,
    decision_type: Optional[str] = None,
) -> list[LedgerRecord]:
    """Filter resolved records by one or more criteria."""
    out = records
    if status:
        out = [r for r in out if r.link.status == status]
    if strength:
        out = [r for r in out if r.link.strength == strength]
    if researcher:
        out = [r for r in out if r.insight.researcher.lower() == researcher.lower()]
    if team:
        out = [r for r in out if r.decision.team.lower() == team.lower()]
    if tag:
        out = [r for r in out if tag.lower() in [t.lower() for t in r.insight.tags]]
    if decision_type:
        out = [r for r in out if r.decision.decision_type == decision_type]
    return out


def compute_summary(ledger: Ledger, records: Optional[list[LedgerRecord]] = None) -> LedgerSummary:
    """
    Compute aggregate stats.
    Proposed links are counted separately and excluded from activation rate.
    """
    if records is None:
        records = resolve_records(ledger, include_proposed=False)

    # Proposed count is always from the full ledger
    proposed_count = len(ledger.list_proposed())

    status_counts: Counter = Counter(r.link.status for r in records)
    strength_counts: Counter = Counter(r.link.strength for r in records)

    adopted = status_counts.get(LinkStatus.ADOPTED.value, 0)
    partial = status_counts.get(LinkStatus.PARTIAL.value, 0)
    declined = status_counts.get(LinkStatus.DECLINED.value, 0)
    denominator = adopted + partial + declined
    activation_rate = (adopted + 0.5 * partial) / denominator if denominator else 0.0

    researcher_counts: Counter = Counter(r.insight.researcher for r in records if r.insight.researcher)
    team_counts: Counter = Counter(r.decision.team for r in records if r.decision.team)
    tag_counts: Counter = Counter(t for r in records for t in r.insight.tags)

    return LedgerSummary(
        total_insights=len(ledger.list_insights()),
        total_decisions=len(ledger.list_decisions()),
        total_links=len(records),
        proposed_count=proposed_count,
        adopted=adopted,
        partial=partial,
        declined=declined,
        deferred=status_counts.get(LinkStatus.DEFERRED.value, 0),
        pending=status_counts.get(LinkStatus.PENDING.value, 0),
        high_strength=strength_counts.get(LinkStrength.HIGH.value, 0),
        medium_strength=strength_counts.get(LinkStrength.MEDIUM.value, 0),
        low_strength=strength_counts.get(LinkStrength.LOW.value, 0),
        activation_rate=round(activation_rate, 3),
        top_researchers=[r for r, _ in researcher_counts.most_common(5)],
        top_teams=[t for t, _ in team_counts.most_common(5)],
        top_tags=[t for t, _ in tag_counts.most_common(8)],
    )


def insight_influence_score(insight: Insight, records: list[LedgerRecord]) -> float:
    """
    Influence score = Σ (strength_weight × status_weight × confidence).
    Proposed links excluded.
    """
    strength_weights = {
        LinkStrength.HIGH.value: 1.0,
        LinkStrength.MEDIUM.value: 0.6,
        LinkStrength.LOW.value: 0.3,
    }
    status_weights = {
        LinkStatus.ADOPTED.value: 1.0,
        LinkStatus.PARTIAL.value: 0.5,
        LinkStatus.DECLINED.value: 0.0,
        LinkStatus.DEFERRED.value: 0.25,
        LinkStatus.PENDING.value: 0.1,
    }
    score = 0.0
    for r in records:
        if r.insight.id == insight.id and r.link.status != LinkStatus.PROPOSED.value:
            sw = strength_weights.get(r.link.strength, 0.3)
            stw = status_weights.get(r.link.status, 0.0)
            score += sw * stw * insight.confidence
    return round(score, 3)


def ranked_insights(ledger: Ledger) -> list[tuple[Insight, float]]:
    """Return insights sorted by influence score descending."""
    records = resolve_records(ledger, include_proposed=False)
    scored = [(ins, insight_influence_score(ins, records)) for ins in ledger.list_insights()]
    return sorted(scored, key=lambda x: x[1], reverse=True)
