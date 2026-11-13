# insight-ledger

**CPR Orbital #39 — S6: Pre-study & impact**

A manual log for connecting research insights to product decisions. Closes the research-to-impact loop.

Research that can't be traced to outcomes disappears. `insight-ledger` gives you a structured, offline-first notebook that records which findings informed which decisions — with status tracking, influence scoring, and optional LLM-generated provenance notes. No automatic linkage. No integrations. Just a researcher's ledger, made queryable.

---

## The problem

Studies get done. Insights get written up. Decisions get made. And then the causal thread dissolves. Six months later no one can say whether a feature was research-backed or instinct-backed — and the next budget review treats research as optional.

`insight-ledger` is the simplest possible intervention: a structured log where researchers manually record the connection between what they found and what the team decided.

---

## Features

- **Manual log** — researchers record insight→decision links in their own words; no automatic linkage or influence-weight calculation
- **Status tracking** — `adopted`, `partial`, `declined`, `deferred`, `pending` per link
- **Strength rating** — `high`, `medium`, `low`
- **Generic reference field** — paste any ticket ID, doc URL, or identifier; no tool coupling
- **Influence scoring** — rank insights by weighted impact across their linked decisions
- **Adoption rate** — aggregate metric across the ledger corpus
- **Filterable log** — filter by status, strength, researcher, team, or tag
- **LLM provenance notes** — optional auto-generated causal sentence per link
- **LLM ledger narrative** — optional executive summary of the ledger corpus
- **JSON persistence** — human-readable, version-controllable ledger file
- **Streamlit UI** — Dashboard, Ledger, Ranked Insights, Export
- **Click CLI** — `summary`, `list`, `log-insight`, `log-decision`, `link`, `ranked`, `export`, `demo`
- **No API key required** — full rule-based core; LLM layer optional, on by default when a key is present

---

## Install

```bash
pip install insight-ledger

# With Streamlit UI
pip install "insight-ledger[ui]"

# With LLM enrichment
pip install "insight-ledger[llm]"

# Full dev install
pip install "insight-ledger[dev]"
```

---

## Quick start

### Run the demo (synthetic dataset)

```bash
insight-ledger demo
```

> **Transparency note:** The `--demo` dataset is entirely fabricated. It exists for testing and illustration. Use `--store` for real data.

### Summary

```bash
insight-ledger summary --store my_ledger.json
```

### Log an insight

```bash
insight-ledger log-insight \
  --store my_ledger.json \
  --title "Navigation confusion in onboarding" \
  --summary "7 of 8 participants couldn't find Projects within 90s" \
  --study "Q1 Usability Study" \
  --researcher "Alice"
```

### Log a decision

```bash
insight-ledger log-decision \
  --store my_ledger.json \
  --title "Add persistent sidebar nav" \
  --description "Fixed sidebar entry for Projects" \
  --type design \
  --owner "Priya" \
  --team "Growth" \
  --reference "https://docs.example.com/sidebar-spec"
```

The `--reference` field is a free-form string — paste a doc URL, a spec title, a brief ID, a Notion page link, anything. The ledger stores it and displays it; it does nothing else with it.

### Link insight to decision

```bash
insight-ledger link \
  --store my_ledger.json \
  --insight-id i001 \
  --decision-id d001 \
  --status adopted \
  --strength high \
  --rationale "Navigation study directly drove the sidebar redesign spec."
```

### Filter and query

```bash
insight-ledger list --store my_ledger.json --status adopted
insight-ledger list --store my_ledger.json --researcher "Alice"
insight-ledger list --store my_ledger.json --team "Growth"
insight-ledger ranked --store my_ledger.json
```

### Export

```bash
insight-ledger export --store my_ledger.json --out export.json
```

### Streamlit UI

```bash
streamlit run app.py
```

---

## LLM enrichment

Set any one environment variable to activate optional LLM enrichment:

```bash
export ANTHROPIC_API_KEY=sk-...    # anthropic/claude-opus-4-7
export GEMINI_API_KEY=...          # gemini/gemini-4-argon
export OPENAI_API_KEY=sk-...       # openai/gpt-5.5
```

When a key is detected, the `link` command can generate a single-sentence causal provenance note, and `summary` can generate an executive narrative. All LLM functions fail gracefully if no key is present.

---

## Python API

```python
from insight_ledger import (
    Ledger, compute_summary, filter_records, ranked_insights, resolve_records,
    Insight, Decision, InsightLink,
)

ledger = Ledger(store_path="my_ledger.json")

# Log an insight
ins = Insight(title="Navigation confusion", study_name="Q1 Usability",
              researcher="Alice", tags=["onboarding"], confidence=0.9)
ledger.add_insight(ins)

# Log a decision
dec = Decision(title="Add sidebar nav", decision_type="design",
               owner="Priya", team="Growth", reference="https://docs.example.com/sidebar-spec")
ledger.add_decision(dec)

# Link them manually
link = InsightLink(insight_id=ins.id, decision_id=dec.id,
                   status="adopted", strength="high",
                   rationale="Navigation study drove the sidebar spec.")
ledger.add_link(link)

# Query
records = resolve_records(ledger)
s = compute_summary(ledger, records)
print(f"Adoption rate: {s.adoption_rate * 100:.0f}%")

for ins, score in ranked_insights(ledger):
    print(f"{ins.title}: {score:.2f}")
```

---

## Data model

| Entity | Key fields |
|---|---|
| `Insight` | title, summary, study_name, researcher, tags, confidence |
| `Decision` | title, decision_type, owner, team, reference (free-form) |
| `InsightLink` | insight_id, decision_id, status, strength, rationale (researcher's words) |

**Status:** `adopted` · `partial` · `declined` · `deferred` · `pending`

**Strength:** `high` · `medium` · `low`

**Decision types:** `feature` · `design` · `priority` · `strategy` · `process` · `kill`

---

## Influence scoring

Each insight receives a score = Σ `(strength_weight × status_weight × confidence)` across linked decisions.

| Strength | Weight | Status | Weight |
|---|---|---|---|
| high | 1.0 | adopted | 1.0 |
| medium | 0.6 | partial | 0.5 |
| low | 0.3 | deferred | 0.25 |
| | | pending | 0.1 |
| | | declined | 0.0 |

---

## Part of the CPR Ecosystem

`insight-ledger` is **Tool #39 of 40** in the [CPR Orbital Series](https://github.com/kgkazakos) — open-source Python infrastructure for AI-native product research.

**Related tools:**
- [`evidence-chain`](https://github.com/kgkazakos/evidence-chain) — claim-to-evidence provenance through layered research reports
- [`research-rubric`](https://github.com/kgkazakos/research-rubric) — qualitative research quality evaluation
- [`insight-differ`](https://github.com/kgkazakos/insight-differ) — contradiction and gap detection across reports
- [`stakeholder-brief-writer`](https://github.com/kgkazakos/stakeholder-brief-writer) — auto-generates one-page executive summaries

Built as part of [Computational Product Research (CPR)](https://kgkazakos.github.io).

---

## License

MIT © Kostas Kazakos
