"""
LLM enrichment for insight-ledger.

Backends: anthropic/claude-opus-4-7, gemini/gemini-3.1-pro-preview, openai/gpt-5.5
All via LiteLLM. Fails gracefully when no API key is present.
LLM enrichment is ON by default when a key is detected.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import date
from typing import TYPE_CHECKING, Optional

from .models import InsightLink, LedgerRecord, LedgerSummary, LinkStatus

if TYPE_CHECKING:
    from .engine import Ledger
    from .models import Decision, Insight

_AVAILABLE_BACKEND: Optional[str] = None
_LITELLM_OK: bool = False


def _detect_backend() -> Optional[str]:
    global _AVAILABLE_BACKEND, _LITELLM_OK
    if _AVAILABLE_BACKEND:
        return _AVAILABLE_BACKEND
    try:
        import litellm  # noqa: F401
        _LITELLM_OK = True
    except ImportError:
        return None
    key_map = {
        "anthropic/claude-opus-4-7": "ANTHROPIC_API_KEY",
        "gemini/gemini-3.1-pro-preview": "GEMINI_API_KEY",
        "openai/gpt-5.5": "OPENAI_API_KEY",
    }
    for backend, env_var in key_map.items():
        if os.environ.get(env_var):
            _AVAILABLE_BACKEND = backend
            return backend
    return None


def available_backends() -> list[str]:
    """Return backends for which an API key is present."""
    try:
        import litellm  # noqa: F401
    except ImportError:
        return []
    key_map = {
        "anthropic/claude-opus-4-7": "ANTHROPIC_API_KEY",
        "gemini/gemini-3.1-pro-preview": "GEMINI_API_KEY",
        "openai/gpt-5.5": "OPENAI_API_KEY",
    }
    return [b for b, k in key_map.items() if os.environ.get(k)]


def _call_llm(prompt: str, backend: str, max_tokens: int = 600) -> Optional[str]:
    try:
        import litellm
        resp = litellm.completion(
            model=backend,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
        )
        return resp.choices[0].message.content.strip()
    except Exception:
        return None


# ── Manual link enrichment ────────────────────────────────────────────────────

def generate_link_note(
    insight: "Insight",
    decision: "Decision",
    link: InsightLink,
    backend: Optional[str] = None,
) -> Optional[str]:
    """
    Generate a single-sentence provenance note for a manually logged link.
    """
    backend = backend or _detect_backend()
    if not backend:
        return None

    prompt = f"""You are a product research analyst writing a one-sentence provenance note.

Insight: "{insight.title}"
Summary: {insight.summary}
Study: {insight.study_name} ({insight.study_date or 'date unknown'})
Evidence: {insight.raw_evidence or '(none provided)'}

Decision: "{decision.title}"
Type: {decision.decision_type}
Description: {decision.description}

Status: {link.status} | Strength: {link.strength}
Researcher rationale: {link.rationale or '(none)'}

Write ONE precise sentence (max 40 words) explaining the causal chain from insight to decision. Be specific. Do not start with 'The insight' or 'This insight'."""

    return _call_llm(prompt, backend, max_tokens=120)


def generate_ledger_narrative(
    summary: LedgerSummary,
    records: list[LedgerRecord],
    backend: Optional[str] = None,
) -> Optional[str]:
    """Generate a short executive narrative of the ledger."""
    backend = backend or _detect_backend()
    if not backend:
        return None

    adopted_examples = [
        f'"{r.insight.title}" → {r.decision.title}'
        for r in records
        if r.link.status == "adopted"
    ][:3]

    prompt = f"""You are a research operations lead writing a brief ledger narrative.

Stats:
- {summary.total_insights} insights, {summary.total_decisions} decisions, {summary.total_links} confirmed links
- {summary.proposed_count} links awaiting arbitration
- {summary.adopted} adopted, {summary.partial} partial, {summary.declined} declined, {summary.deferred} deferred
- Activation rate: {summary.activation_rate * 100:.0f}%
- Top researchers: {', '.join(summary.top_researchers[:3]) or 'n/a'}
- Top teams: {', '.join(summary.top_teams[:3]) or 'n/a'}

Example adopted activations:
{chr(10).join(adopted_examples) if adopted_examples else '(none yet)'}

Write 3–4 sentences for a research director. Be precise and honest. Note gaps or watch-outs. No bullet points."""

    return _call_llm(prompt, backend, max_tokens=300)


# ── Auto-proposal ─────────────────────────────────────────────────────────────

def propose_links(
    ledger: "Ledger",
    top_k: int = 5,
    threshold: float = 0.5,
    backend: Optional[str] = None,
) -> list[InsightLink]:
    """
    Auto-propose insight→decision activation links using a single LLM call.

    The LLM receives all insights and decisions, knows which pairs already have
    links, and returns the top_k most likely unlinked connections with confidence
    scores and rationales. Only proposals above `threshold` are returned.

    Returns a list of InsightLink objects with status='proposed' and
    auto_proposed=True. Does NOT save them to the ledger — the caller does that.
    """
    backend = backend or _detect_backend()
    if not backend:
        return []

    insights = ledger.list_insights()
    decisions = ledger.list_decisions()
    existing = ledger.existing_pairs()

    if not insights or not decisions:
        return []

    # Build insight and decision summaries for the prompt
    insight_lines = "\n".join(
        f'{ins.id}: "{ins.title}" — {ins.summary[:120]}'
        for ins in insights
    )
    decision_lines = "\n".join(
        f'{dec.id}: "{dec.title}" [{dec.decision_type}] — {dec.description[:100]}'
        for dec in decisions
    )
    existing_pairs_str = ", ".join(f"{a}→{b}" for a, b in existing) or "(none)"

    prompt = f"""You are a research operations analyst identifying likely research activation patterns.

INSIGHTS:
{insight_lines}

DECISIONS:
{decision_lines}

ALREADY LINKED PAIRS (do NOT propose these):
{existing_pairs_str}

Task: Identify the top {top_k} unlinked insight→decision pairs most likely to have a genuine causal connection — where the insight plausibly influenced or could have influenced the decision.

For each pair, provide:
- insight_id: the insight ID
- decision_id: the decision ID
- confidence: float 0.0–1.0 (your confidence in a genuine causal link)
- rationale: one precise sentence explaining the likely connection

Return ONLY a JSON array. No markdown, no preamble, no explanation outside the JSON.
Example format:
[{{"insight_id": "i001", "decision_id": "d003", "confidence": 0.72, "rationale": "..."}}]

Only include pairs where confidence >= {threshold}. If none meet the threshold, return an empty array []."""

    raw = _call_llm(prompt, backend, max_tokens=800)
    if not raw:
        return []

    try:
        clean = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
        proposals = json.loads(clean)
    except (json.JSONDecodeError, ValueError):
        return []

    results = []
    for p in proposals:
        try:
            insight_id = p["insight_id"]
            decision_id = p["decision_id"]
            confidence = float(p.get("confidence", 0.0))
            rationale = p.get("rationale", "")

            # Skip if below threshold, already linked, or IDs don't exist
            if confidence < threshold:
                continue
            if (insight_id, decision_id) in existing:
                continue
            if not ledger.get_insight(insight_id) or not ledger.get_decision(decision_id):
                continue

            link = InsightLink(
                id=str(uuid.uuid4())[:8],
                insight_id=insight_id,
                decision_id=decision_id,
                status=LinkStatus.PROPOSED.value,
                strength="medium",                # placeholder; reviewer sets final strength
                rationale=rationale,
                logged_date=str(date.today()),
                auto_proposed=True,
                proposal_confidence=round(confidence, 3),
            )
            results.append(link)
        except (KeyError, TypeError, ValueError):
            continue

    # Sort by confidence descending
    return sorted(results, key=lambda lk: lk.proposal_confidence, reverse=True)
