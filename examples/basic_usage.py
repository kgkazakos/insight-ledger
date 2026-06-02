"""
Basic usage — insight-ledger.

Loads the synthetic demo dataset and demonstrates querying,
filtering, ranking, and summary stats.

All data is fabricated for illustration only.
"""

from insight_ledger import Ledger, compute_summary, filter_records, ranked_insights, resolve_records
from insight_ledger.synthetic import load_synthetic_ledger

ledger = load_synthetic_ledger()
print(f"Loaded: {len(ledger.list_insights())} insights, "
      f"{len(ledger.list_decisions())} decisions, "
      f"{len(ledger.list_links())} links\n")

records = resolve_records(ledger)
s = compute_summary(ledger, records)
print(f"Adoption rate : {s.adoption_rate * 100:.0f}%")
print(f"Adopted: {s.adopted}  Partial: {s.partial}  Declined: {s.declined}  Deferred: {s.deferred}")
print(f"Top researchers: {', '.join(s.top_researchers)}\n")

adopted = filter_records(records, status="adopted")
print(f"Adopted links ({len(adopted)}):")
for r in adopted:
    print(f"  [{r.link.strength}] {r.insight.title!r} → {r.decision.title!r}")
print()

print("Insights ranked by influence:")
for i, (ins, score) in enumerate(ranked_insights(ledger), 1):
    print(f"  {i}. {ins.title!r}  score={score:.2f}  researcher={ins.researcher}")
