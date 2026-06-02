"""insight-ledger — CPR Orbital #39.

A manual + auto-proposed log for connecting research insights to product decisions.
Closes the research activation loop with structure and LLM-assisted discovery.
"""

from .engine import (
    Ledger,
    compute_summary,
    filter_records,
    insight_influence_score,
    ranked_insights,
    resolve_proposals,
    resolve_records,
)
from .models import (
    Decision,
    DecisionType,
    Insight,
    InsightLink,
    LedgerRecord,
    LedgerSummary,
    LinkStatus,
    LinkStrength,
)

__version__ = "0.1.0"
__all__ = [
    "Ledger",
    "Insight",
    "Decision",
    "InsightLink",
    "LedgerRecord",
    "LedgerSummary",
    "LinkStatus",
    "LinkStrength",
    "DecisionType",
    "compute_summary",
    "filter_records",
    "insight_influence_score",
    "ranked_insights",
    "resolve_proposals",
    "resolve_records",
]
