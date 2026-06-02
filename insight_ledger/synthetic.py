"""
Built-in synthetic dataset for insight-ledger.

Disclosure: all data is entirely fabricated for demonstration and testing.
Not real research findings, not real product decisions, not a real organisation.
Replace with your own data via --store or JSON import.
"""

from __future__ import annotations

from .engine import Ledger
from .models import Decision, DecisionType, Insight, InsightLink, LinkStatus, LinkStrength


def load_synthetic_ledger() -> Ledger:
    """Return a pre-populated Ledger with synthetic demo data."""
    ledger = Ledger()

    # ── Insights ──────────────────────────────────────────────────────────────

    insights = [
        Insight(
            id="i001",
            title="Navigation confusion in onboarding flow",
            summary="7 of 8 participants could not locate the Projects section within 90 seconds.",
            study_name="Onboarding Usability Study Q1",
            study_date="2026-01-15",
            researcher="Ana Ferreira",
            tags=["onboarding", "navigation", "usability"],
            raw_evidence="P4: 'I kept looking for a sidebar. I had no idea where projects lived.'",
            confidence=0.92,
        ),
        Insight(
            id="i002",
            title="Notification fatigue causing app abandonment",
            summary="Participants receiving >5 notifications/day showed 62% higher session-drop rates.",
            study_name="Diary Study: Mobile Engagement",
            study_date="2026-02-03",
            researcher="Lena Park",
            tags=["notifications", "engagement", "mobile"],
            raw_evidence="P2: 'I just turned everything off. It was too much.'",
            confidence=0.85,
        ),
        Insight(
            id="i003",
            title="Search relevance poorly matched to mental models",
            summary="Users expected keyword match; ML-ranked results produced confusion and distrust.",
            study_name="Search Behaviour Study",
            study_date="2025-11-20",
            researcher="Tom Reyes",
            tags=["search", "trust", "mental-models"],
            raw_evidence="P6: 'Why is this the top result? It has nothing to do with what I typed.'",
            confidence=0.78,
        ),
        Insight(
            id="i004",
            title="Collaborative editing causes merge anxiety",
            summary="Teams with 4+ editors reported stress around simultaneous editing, fearing data loss.",
            study_name="Collaboration Patterns Study",
            study_date="2026-03-01",
            researcher="Ana Ferreira",
            tags=["collaboration", "editing", "anxiety"],
            raw_evidence="P1: 'I always export before anyone else touches it.'",
            confidence=0.88,
        ),
        Insight(
            id="i005",
            title="Permission model opaque to non-admin users",
            summary="Non-admin users could not predict who could see their content — 5 of 6 wrong.",
            study_name="Permissions Mental Model Study",
            study_date="2026-01-28",
            researcher="Lena Park",
            tags=["permissions", "transparency", "trust"],
            raw_evidence="P3: 'I thought only my team could see this. That's not right?'",
            confidence=0.90,
        ),
        Insight(
            id="i006",
            title="Power users rely on undiscoverable keyboard shortcuts",
            summary="6 of 7 power users in contextual inquiry used shortcuts — none were surfaced in the UI.",
            study_name="Power User Contextual Inquiry",
            study_date="2025-12-10",
            researcher="Tom Reyes",
            tags=["accessibility", "power-users", "shortcuts"],
            raw_evidence="P7: 'Half the things I want don't have shortcuts, or I can't find them.'",
            confidence=0.82,
        ),
    ]

    # ── Decisions ─────────────────────────────────────────────────────────────

    decisions = [
        Decision(
            id="d001",
            title="Add persistent left-nav Projects anchor",
            description="Fixed sidebar entry for Projects, always visible during onboarding.",
            decision_type=DecisionType.DESIGN.value,
            decision_date="2026-02-01",
            owner="Priya Sharma",
            team="Growth",
            reference="design-brief-sidebar-feb-2026",
            outcome_notes="Shipped v2.4. Onboarding CSAT 3.2 → 4.1.",
        ),
        Decision(
            id="d002",
            title="Introduce notification digest mode",
            description="Bundle non-urgent notifications into a daily digest; urgent ones still immediate.",
            decision_type=DecisionType.FEATURE.value,
            decision_date="2026-03-10",
            owner="Marcus Lin",
            team="Platform",
            reference="feature-spec-notification-digest",
            outcome_notes="Beta. 18% reduction in notification-driven uninstalls.",
        ),
        Decision(
            id="d003",
            title="Surface search ranking explanation tooltip",
            description="'Why this result?' tooltip showing the top 3 relevance signals per result.",
            decision_type=DecisionType.DESIGN.value,
            decision_date="2026-01-20",
            owner="Priya Sharma",
            team="Search",
            reference="search-ux-spec-q1-2026",
            outcome_notes="Deferred to Q3 — ML team capacity.",
        ),
        Decision(
            id="d004",
            title="Add edit-lock indicator for active collaborators",
            description="Live avatar presence and section-level edit locks to prevent collision anxiety.",
            decision_type=DecisionType.FEATURE.value,
            decision_date="2026-03-20",
            owner="Hina Yoshida",
            team="Collaboration",
            reference="collab-sprint-brief-mar-2026",
            outcome_notes="In design sprint.",
        ),
        Decision(
            id="d005",
            title="Permissions visibility panel",
            description="'Who can see this?' panel accessible from any content item.",
            decision_type=DecisionType.FEATURE.value,
            decision_date="2026-02-14",
            owner="Marcus Lin",
            team="Trust & Safety",
            reference="https://docs.example.com/permissions-visibility-spec",
            outcome_notes="Shipped v2.5. Permissions support tickets down 34%.",
        ),
        Decision(
            id="d006",
            title="Deprecate legacy search v1",
            description="Kill legacy keyword search in favour of ML-ranked search.",
            decision_type=DecisionType.KILL.value,
            decision_date="2025-12-01",
            owner="Hina Yoshida",
            team="Search",
            reference="search-strategy-dec-2025",
            outcome_notes="Decision predated the study. Reconsidered per i003.",
        ),
    ]

    # ── Confirmed links (manually logged) ────────────────────────────────────

    confirmed_links = [
        InsightLink(
            id="l001",
            insight_id="i001",
            decision_id="d001",
            status=LinkStatus.ADOPTED.value,
            strength=LinkStrength.HIGH.value,
            rationale="Navigation confusion study directly drove the sidebar redesign spec.",
            logged_by="Ana Ferreira",
            logged_date="2026-02-02",
        ),
        InsightLink(
            id="l002",
            insight_id="i002",
            decision_id="d002",
            status=LinkStatus.PARTIAL.value,
            strength=LinkStrength.HIGH.value,
            rationale="Fatigue finding cited in feature brief; digest adopted but per-channel control deferred.",
            logged_by="Lena Park",
            logged_date="2026-03-11",
        ),
        InsightLink(
            id="l003",
            insight_id="i003",
            decision_id="d003",
            status=LinkStatus.DEFERRED.value,
            strength=LinkStrength.MEDIUM.value,
            rationale="Study influenced the tooltip spec but launch deferred to Q3.",
            logged_by="Tom Reyes",
            logged_date="2026-01-22",
        ),
        InsightLink(
            id="l004",
            insight_id="i003",
            decision_id="d006",
            status=LinkStatus.DECLINED.value,
            strength=LinkStrength.LOW.value,
            rationale="Study surfaced post-decision; kill decision was already made.",
            logged_by="Tom Reyes",
            logged_date="2026-01-22",
        ),
        InsightLink(
            id="l005",
            insight_id="i004",
            decision_id="d004",
            status=LinkStatus.ADOPTED.value,
            strength=LinkStrength.HIGH.value,
            rationale="Merge anxiety finding was the primary justification for the edit-lock feature spec.",
            logged_by="Ana Ferreira",
            logged_date="2026-03-21",
        ),
        InsightLink(
            id="l006",
            insight_id="i005",
            decision_id="d005",
            status=LinkStatus.ADOPTED.value,
            strength=LinkStrength.HIGH.value,
            rationale="Permissions opacity study referenced directly in the feature brief.",
            logged_by="Lena Park",
            logged_date="2026-02-15",
        ),
        InsightLink(
            id="l007",
            insight_id="i006",
            decision_id="d001",
            status=LinkStatus.PARTIAL.value,
            strength=LinkStrength.MEDIUM.value,
            rationale="Shortcut discoverability influenced sidebar design; shortcuts themselves not yet addressed.",
            logged_by="Tom Reyes",
            logged_date="2026-02-02",
        ),
    ]

    # ── Auto-proposed links (awaiting arbitration) ────────────────────────────
    # These simulate what the `propose` command would generate.

    proposed_links = [
        InsightLink(
            id="p001",
            insight_id="i002",
            decision_id="d004",
            status=LinkStatus.PROPOSED.value,
            strength=LinkStrength.MEDIUM.value,
            rationale="Notification fatigue patterns may have informed the decision to add presence indicators — both address cognitive overload from ambient team activity.",
            auto_proposed=True,
            proposal_confidence=0.68,
            logged_date="2026-04-01",
        ),
        InsightLink(
            id="p002",
            insight_id="i006",
            decision_id="d003",
            status=LinkStatus.PROPOSED.value,
            strength=LinkStrength.MEDIUM.value,
            rationale="Power user reliance on undiscoverable shortcuts suggests a broader discoverability deficit that the search ranking tooltip may partially address.",
            auto_proposed=True,
            proposal_confidence=0.54,
            logged_date="2026-04-01",
        ),
        InsightLink(
            id="p003",
            insight_id="i001",
            decision_id="d005",
            status=LinkStatus.PROPOSED.value,
            strength=LinkStrength.MEDIUM.value,
            rationale="Navigation confusion in onboarding may have surfaced broader structural opacity issues that informed the permissions visibility panel decision.",
            auto_proposed=True,
            proposal_confidence=0.51,
            logged_date="2026-04-01",
        ),
    ]

    for ins in insights:
        ledger.insights[ins.id] = ins
    for dec in decisions:
        ledger.decisions[dec.id] = dec
    for lk in confirmed_links + proposed_links:
        ledger.links[lk.id] = lk

    return ledger
