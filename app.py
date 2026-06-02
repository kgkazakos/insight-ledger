"""Streamlit UI for insight-ledger · CPR Orbital #39."""

import json
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))

from insight_ledger.engine import (
    Ledger, compute_summary, filter_records,
    ranked_insights, resolve_proposals, resolve_records,
)
from insight_ledger.llm import available_backends, generate_ledger_narrative, propose_links
from insight_ledger.models import Decision, Insight, InsightLink, LinkStatus, LinkStrength
from insight_ledger.synthetic import load_synthetic_ledger

st.set_page_config(
    page_title="insight-ledger · CPR Orbital #39",
    page_icon="📖",
    layout="wide",
)

ACCENT = "#1D9E75"
PROPOSE_COLOR = "#9333ea"

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600&family=DM+Mono:wght@400;500&display=swap');
html, body, [class*="css"] {{ font-family: 'DM Sans', sans-serif; background-color: #faf9f6; color: #1a1a1a; }}
.main .block-container {{ padding-top: 1.2rem; padding-bottom: 2rem; max-width: 1200px; }}
section[data-testid="stSidebar"] {{ background-color: #0f0f0f; }}
section[data-testid="stSidebar"] * {{ color: #e8e8e8 !important; font-family: 'DM Mono', monospace !important; }}
section[data-testid="stSidebar"] .stSelectbox label,
section[data-testid="stSidebar"] .stCheckbox label,
section[data-testid="stSidebar"] .stTextInput label {{
    color: #aaa !important; font-size: 11px !important; text-transform: uppercase; letter-spacing: 0.08em;
}}
.metric-card {{ background: #fff; border: 1px solid #e8e6e1; border-radius: 8px; padding: 12px 14px; text-align: center; }}
.metric-card .val {{ font-family: 'DM Mono', monospace; font-size: 22px; font-weight: 500; color: {ACCENT}; }}
.metric-card .val-propose {{ font-family: 'DM Mono', monospace; font-size: 22px; font-weight: 500; color: {PROPOSE_COLOR}; }}
.metric-card .lbl {{ font-size: 9px; color: #aaa; text-transform: uppercase; letter-spacing: 0.07em; margin-top: 3px; }}
.ledger-row {{ background: #fff; border: 1px solid #e8e6e1; border-left: 3px solid {ACCENT};
    border-radius: 6px; padding: 12px 16px; margin-bottom: 8px; }}
.proposal-row {{ background: #fdf4ff; border: 1px solid #e9d5ff; border-left: 3px solid {PROPOSE_COLOR};
    border-radius: 6px; padding: 12px 16px; margin-bottom: 8px; }}
.insight-title {{ font-family: 'DM Mono', monospace; font-size: 12px; font-weight: 500; color: #1a1a1a; }}
.decision-title {{ font-size: 13px; color: #444; margin: 4px 0; }}
.meta {{ font-size: 11px; color: #999; font-family: 'DM Mono', monospace; }}
.conf-bar-bg {{ height: 4px; background: #e9d5ff; border-radius: 2px; margin: 6px 0; }}
.badge {{ display: inline-block; padding: 1px 7px; border-radius: 4px; font-size: 10px;
    font-family: 'DM Mono', monospace; font-weight: 500; margin-right: 4px; }}
.badge-adopted  {{ background: #e1f5ee; color: #0f6e56; }}
.badge-partial  {{ background: #fef9e7; color: #85640b; }}
.badge-declined {{ background: #fdecea; color: #a0231b; }}
.badge-deferred {{ background: #e8f4fd; color: #185fa5; }}
.badge-pending  {{ background: #f5f5f5; color: #666; }}
.badge-proposed {{ background: #f3e8ff; color: #7e22ce; }}
.badge-high     {{ background: #e1f5ee; color: #0f6e56; }}
.badge-medium   {{ background: #fff3e0; color: #854f0b; }}
.badge-low      {{ background: #f5f5f5; color: #888; }}
.narrative-box {{ background: #f0faf5; border: 1px solid #b8e6d4; border-radius: 8px;
    padding: 14px 16px; font-size: 13px; line-height: 1.7; color: #1a1a1a; margin-bottom: 16px; }}
.section-header {{ font-family: 'DM Mono', monospace; font-size: 9px; text-transform: uppercase;
    letter-spacing: 0.1em; color: #aaa; border-bottom: 1px solid #e8e6e1;
    padding-bottom: 5px; margin: 20px 0 12px; }}
.propose-banner {{ background: #fdf4ff; border: 1px solid #e9d5ff; border-radius: 8px;
    padding: 10px 14px; font-size: 12px; color: #7e22ce; margin-bottom: 14px; }}
</style>
""", unsafe_allow_html=True)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("**● CPR ORBITAL**")
    st.markdown("`insight-ledger · #39`")
    st.markdown("---")
    st.markdown("**NAVIGATE**")
    view = st.radio(
        "", ["Dashboard", "Ledger", "Proposals", "Ranked Insights", "Export"],
        label_visibility="collapsed",
    )
    st.markdown("---")
    st.markdown("**DATA**")
    use_demo = st.checkbox("Use synthetic demo data", value=True)
    store_path = None
    if not use_demo:
        store_path = st.text_input("Ledger file path", value="ledger.json")

    st.markdown("**FILTERS**")
    status_filter = st.selectbox(
        "Status",
        ["All"] + [s.value for s in LinkStatus if s != LinkStatus.PROPOSED],
    )
    strength_filter = st.selectbox("Strength", ["All"] + [s.value for s in LinkStrength])
    researcher_filter = st.text_input("Researcher", value="")
    team_filter = st.text_input("Team", value="")
    tag_filter = st.text_input("Tag", value="")

    st.markdown("---")
    st.markdown("**LLM ENRICHMENT**")
    use_llm = st.checkbox("Enable LLM narrative", value=True)
    backends = available_backends()
    chosen_backend = None
    if backends:
        chosen_backend = st.selectbox("Backend", backends)
    else:
        st.caption("No API key — rule-based only")
    st.markdown("---")
    st.caption("v0.1.0 · MIT · kgkazakos")


# ── Load ledger ───────────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def _demo_data():
    return load_synthetic_ledger().export_json()


def _load_ledger() -> Ledger:
    if use_demo:
        raw = _demo_data()
        ledger = Ledger()
        ledger.insights = {v["id"]: Insight(**v) for v in raw["insights"]}
        ledger.decisions = {v["id"]: Decision(**v) for v in raw["decisions"]}
        ledger.links = {v["id"]: InsightLink(**v) for v in raw["links"]}
        return ledger
    return Ledger(store_path=store_path)


ledger = _load_ledger()
all_records = resolve_records(ledger, include_proposed=False)
filtered = filter_records(
    all_records,
    status=None if status_filter == "All" else status_filter,
    strength=None if strength_filter == "All" else strength_filter,
    researcher=researcher_filter.strip() or None,
    team=team_filter.strip() or None,
    tag=tag_filter.strip() or None,
)
summary = compute_summary(ledger, filtered)
proposals = resolve_proposals(ledger)

if use_llm and chosen_backend and filtered:
    summary.llm_narrative = generate_ledger_narrative(summary, filtered, backend=chosen_backend)


def _badge(cls, text):
    return f'<span class="badge badge-{cls}">{text}</span>'


# ── DASHBOARD ─────────────────────────────────────────────────────────────────
if view == "Dashboard":
    st.markdown("## insight-ledger")
    st.caption("CPR Orbital #39 — manual + auto-proposed log for research activation")
    if use_demo:
        st.info("⚡ Synthetic demo data — all insights and decisions are fabricated.", icon="ℹ️")

    if proposals:
        st.markdown(
            f'<div class="propose-banner">🔮 <strong>{len(proposals)} proposed link(s)</strong> '
            f'awaiting arbitration — review them in the <strong>Proposals</strong> tab.</div>',
            unsafe_allow_html=True,
        )

    cols = st.columns(6)
    stats = [
        ("Insights", summary.total_insights, ACCENT),
        ("Decisions", summary.total_decisions, ACCENT),
        ("Confirmed", summary.total_links, ACCENT),
        ("Awaiting review", summary.proposed_count, PROPOSE_COLOR),
        ("Activation rate", f"{summary.activation_rate * 100:.0f}%", ACCENT),
        ("High-strength", summary.high_strength, ACCENT),
    ]
    for col, (lbl, val, color) in zip(cols, stats):
        with col:
            val_class = "val-propose" if color == PROPOSE_COLOR else "val"
            st.markdown(
                f'<div class="metric-card"><div class="{val_class}">{val}</div>'
                f'<div class="lbl">{lbl}</div></div>',
                unsafe_allow_html=True,
            )

    st.markdown('<div class="section-header">Status breakdown (confirmed links)</div>', unsafe_allow_html=True)
    bcols = st.columns(5)
    for col, (lbl, val, color) in zip(bcols, [
        ("adopted", summary.adopted, "#1D9E75"),
        ("partial", summary.partial, "#d97706"),
        ("declined", summary.declined, "#dc2626"),
        ("deferred", summary.deferred, "#2563eb"),
        ("pending", summary.pending, "#9ca3af"),
    ]):
        with col:
            st.markdown(f"""<div style="text-align:center;padding:8px">
<div style="font-family:'DM Mono',monospace;font-size:20px;font-weight:500;color:{color}">{val}</div>
<div style="font-size:9px;color:#aaa;text-transform:uppercase;letter-spacing:.05em">{lbl}</div>
</div>""", unsafe_allow_html=True)

    if summary.llm_narrative:
        st.markdown('<div class="section-header">Narrative</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="narrative-box">{summary.llm_narrative}</div>', unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown('<div class="section-header">Top researchers</div>', unsafe_allow_html=True)
        for r in summary.top_researchers:
            st.markdown(f"`{r}`")
    with c2:
        st.markdown('<div class="section-header">Top teams</div>', unsafe_allow_html=True)
        for t in summary.top_teams:
            st.markdown(f"`{t}`")
    with c3:
        st.markdown('<div class="section-header">Top tags</div>', unsafe_allow_html=True)
        st.markdown(" ".join([f'`{t}`' for t in summary.top_tags]))


# ── LEDGER ────────────────────────────────────────────────────────────────────
elif view == "Ledger":
    st.markdown("## Ledger")
    st.caption(f"{len(filtered)} confirmed records")
    if not filtered:
        st.info("No records match the current filters.")
    else:
        for r in filtered:
            tags_html = " ".join([f'<span class="badge badge-pending">{t}</span>' for t in r.insight.tags[:4]])
            ref_html = f'&nbsp;·&nbsp; ref: <code>{r.decision.reference}</code>' if r.decision.reference else ''
            st.markdown(f"""<div class="ledger-row">
<div class="insight-title">🔍 {r.insight.title}</div>
<div class="decision-title">→ {r.decision.title}</div>
<div class="meta">
  {_badge(r.link.status, r.link.status)}
  {_badge(r.link.strength, r.link.strength)}
  {tags_html}
  &nbsp;·&nbsp; {r.insight.researcher or '—'} → {r.decision.team or '—'}{ref_html}
</div>
{f'<div class="meta" style="margin-top:6px;color:#555">{r.link.rationale}</div>' if r.link.rationale else ''}
{f'<div class="meta" style="margin-top:4px;color:{ACCENT}">{r.link.llm_note}</div>' if r.link.llm_note else ''}
</div>""", unsafe_allow_html=True)


# ── PROPOSALS ─────────────────────────────────────────────────────────────────
elif view == "Proposals":
    st.markdown("## Proposals")
    st.caption("Auto-generated by the LLM · awaiting human arbitration · excluded from activation rate")

    if not proposals:
        st.success("No pending proposals — all auto-proposed links have been reviewed.")
    else:
        st.info(
            f"**{len(proposals)} proposal(s)** sorted by confidence. "
            "Review each one and confirm, decline, or defer. "
            "Confirmed links are added to the ledger and count toward activation rate.",
            icon="🔮",
        )

        for r in proposals:
            conf_pct = int(r.link.proposal_confidence * 100)
            conf_color = "#1D9E75" if conf_pct >= 70 else "#d97706" if conf_pct >= 50 else "#9ca3af"
            st.markdown(f"""<div class="proposal-row">
<div class="insight-title">🔍 {r.insight.title}</div>
<div class="decision-title">→ {r.decision.title} [{r.decision.decision_type}]</div>
<div style="display:flex;align-items:center;gap:8px;margin:6px 0">
  <span style="font-family:'DM Mono',monospace;font-size:11px;color:{conf_color};font-weight:500">
    conf {r.link.proposal_confidence:.2f}
  </span>
  <div style="flex:1;height:4px;background:#e9d5ff;border-radius:2px">
    <div style="width:{conf_pct}%;height:100%;background:{conf_color};border-radius:2px"></div>
  </div>
</div>
<div class="meta" style="color:#7e22ce">{r.link.rationale}</div>
<div class="meta" style="margin-top:4px">{r.insight.researcher} · {r.insight.study_name}</div>
</div>""", unsafe_allow_html=True)

            with st.expander("Arbitrate this proposal"):
                new_status = st.selectbox(
                    "Decision",
                    ["adopted", "partial", "declined", "deferred"],
                    key=f"status_{r.link.id}",
                )
                new_strength = st.selectbox(
                    "Strength",
                    ["high", "medium", "low"],
                    index=1,
                    key=f"strength_{r.link.id}",
                )
                rationale_override = st.text_input(
                    "Your rationale (leave blank to keep LLM's)",
                    key=f"rat_{r.link.id}",
                )
                if st.button("Confirm", key=f"confirm_{r.link.id}"):
                    r.link.status = new_status
                    r.link.strength = new_strength
                    if rationale_override.strip():
                        r.link.rationale = rationale_override.strip()
                    if not use_demo and store_path:
                        ledger.links[r.link.id] = r.link
                        ledger._save()
                    st.success(f"Confirmed as **{new_status}** / {new_strength}")
                    st.rerun()


# ── RANKED ────────────────────────────────────────────────────────────────────
elif view == "Ranked Insights":
    st.markdown("## Insights Ranked by Influence")
    st.caption("Score = Σ (strength × status × confidence) — confirmed links only")
    for i, (ins, score) in enumerate(ranked_insights(ledger), 1):
        bar = "█" * int(score * 5) + "░" * (5 - int(score * 5))
        st.markdown(f"""<div class="ledger-row">
<div style="display:flex;justify-content:space-between;align-items:baseline">
  <div class="insight-title">#{i} &nbsp; {ins.title}</div>
  <div style="font-family:'DM Mono',monospace;font-size:13px;color:{ACCENT}">{score:.2f} &nbsp;{bar}</div>
</div>
<div style="font-size:12px;color:#666;margin:5px 0">{ins.summary[:120]}…</div>
<div class="meta">{ins.researcher} · {ins.study_name} · conf {ins.confidence:.0%}</div>
</div>""", unsafe_allow_html=True)


# ── EXPORT ────────────────────────────────────────────────────────────────────
elif view == "Export":
    st.markdown("## Export")
    payload = json.dumps(ledger.export_json(), indent=2)
    st.download_button("Download JSON", payload, "ledger.json", "application/json")
    st.code(payload[:1200] + "\n...", language="json")
