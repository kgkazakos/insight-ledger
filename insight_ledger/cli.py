"""
CLI for insight-ledger.

Commands:
  summary       Aggregate ledger statistics
  list          Filterable log of confirmed links
  log-insight   Add a research insight
  log-decision  Add a product decision
  link          Manually log an insight→decision link
  propose       Auto-propose links via LLM (single call, human arbitration required)
  review        Interactive review queue for proposed links
  ranked        Insights ranked by influence score
  export        Export ledger to JSON
  demo          Load and summarise the built-in synthetic dataset
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path
from typing import Optional

import click
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .engine import (
    Ledger,
    compute_summary,
    filter_records,
    ranked_insights,
    resolve_proposals,
    resolve_records,
)
from .llm import available_backends, generate_ledger_narrative, propose_links
from .models import Decision, DecisionType, Insight, InsightLink, LinkStatus, LinkStrength
from .synthetic import load_synthetic_ledger

console = Console()
ACCENT = "#1D9E75"


def _make_ledger(store_path: Optional[str], demo: bool) -> Ledger:
    if demo:
        return load_synthetic_ledger()
    return Ledger(store_path=store_path)


def _status_colour(status: str) -> str:
    return {
        "adopted": "green", "partial": "yellow", "declined": "red",
        "deferred": "cyan", "pending": "white", "proposed": "magenta",
    }.get(status, "white")


def _strength_bar(strength: str) -> str:
    return {"high": "●●●", "medium": "●●○", "low": "●○○"}.get(strength, "○○○")


@click.group()
@click.version_option("0.1.0", prog_name="insight-ledger")
def cli() -> None:
    """CPR Orbital #39 — insight-ledger.

    Manual + auto-proposed log connecting research insights to product decisions.
    """


# ── summary ───────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--store", default=None)
@click.option("--demo", is_flag=True)
@click.option("--llm/--no-llm", default=True, show_default=True)
@click.option("--backend", default=None)
@click.option("--json-output", is_flag=True)
def summary(store: Optional[str], demo: bool, llm: bool, backend: Optional[str], json_output: bool) -> None:
    """Print aggregate ledger statistics."""
    ledger = _make_ledger(store, demo)
    records = resolve_records(ledger)
    s = compute_summary(ledger, records)

    if llm:
        backends = available_backends()
        chosen = backend or (backends[0] if backends else None)
        if chosen:
            s.llm_narrative = generate_ledger_narrative(s, records, backend=chosen)

    if json_output:
        click.echo(json.dumps(s.to_dict(), indent=2))
        return

    console.print(Panel(
        "[bold]insight-ledger[/bold] · CPR Orbital #39",
        subtitle="[dim]Research activation log[/dim]",
        border_style=ACCENT,
    ))
    t = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    t.add_column("k", style="dim")
    t.add_column("v", style="bold")
    for label, val in [
        ("Insights", s.total_insights), ("Decisions", s.total_decisions),
        ("Confirmed links", s.total_links),
        ("Awaiting arbitration", f"[magenta]{s.proposed_count}[/magenta]"),
        ("Activation rate", f"{s.activation_rate * 100:.0f}%"),
        ("Adopted", f"[green]{s.adopted}[/green]"),
        ("Partial", f"[yellow]{s.partial}[/yellow]"),
        ("Declined", f"[red]{s.declined}[/red]"),
        ("Deferred", f"[cyan]{s.deferred}[/cyan]"),
        ("Top researchers", ", ".join(s.top_researchers) or "—"),
        ("Top teams", ", ".join(s.top_teams) or "—"),
    ]:
        t.add_row(label, str(val))
    console.print(t)

    if s.proposed_count:
        console.print(f"[magenta]ℹ {s.proposed_count} proposed link(s) awaiting review — run `insight-ledger review`[/magenta]")

    if s.llm_narrative:
        console.print(Panel(s.llm_narrative, title="[dim]narrative[/dim]", border_style="dim"))


# ── list ──────────────────────────────────────────────────────────────────────

@cli.command("list")
@click.option("--store", default=None)
@click.option("--demo", is_flag=True)
@click.option("--status", default=None, type=click.Choice([s.value for s in LinkStatus]))
@click.option("--strength", default=None, type=click.Choice([s.value for s in LinkStrength]))
@click.option("--researcher", default=None)
@click.option("--team", default=None)
@click.option("--tag", default=None)
@click.option("--include-proposed", is_flag=True, help="Also show proposed links")
@click.option("--json-output", is_flag=True)
def list_records(
    store: Optional[str], demo: bool, status: Optional[str], strength: Optional[str],
    researcher: Optional[str], team: Optional[str], tag: Optional[str],
    include_proposed: bool, json_output: bool,
) -> None:
    """List ledger records with optional filters."""
    ledger = _make_ledger(store, demo)
    records = resolve_records(ledger, include_proposed=include_proposed)
    records = filter_records(records, status=status, strength=strength,
                             researcher=researcher, team=team, tag=tag)

    if json_output:
        click.echo(json.dumps([r.to_dict() for r in records], indent=2))
        return

    if not records:
        console.print("[dim]No records match the current filters.[/dim]")
        return

    table = Table(box=box.SIMPLE_HEAVY, header_style=f"bold {ACCENT}")
    table.add_column("Insight", max_width=34)
    table.add_column("Decision", max_width=28)
    table.add_column("Status", width=10)
    table.add_column("Str", width=5)
    table.add_column("Conf", width=5)
    table.add_column("Researcher", max_width=14)

    for r in records:
        colour = _status_colour(r.link.status)
        conf = f"{r.link.proposal_confidence:.2f}" if r.link.auto_proposed else "—"
        table.add_row(
            r.insight.title[:34],
            r.decision.title[:28],
            f"[{colour}]{r.link.status}[/{colour}]",
            _strength_bar(r.link.strength),
            conf,
            r.insight.researcher or "—",
        )
    console.print(table)
    console.print(f"[dim]{len(records)} records[/dim]")


# ── log-insight ───────────────────────────────────────────────────────────────

@cli.command("log-insight")
@click.option("--store", required=True)
@click.option("--title", prompt=True)
@click.option("--summary", "summary_text", prompt=True)
@click.option("--study", prompt=True)
@click.option("--researcher", prompt=True)
@click.option("--date", "study_date", default=str(date.today()))
@click.option("--tags", default="")
@click.option("--evidence", default="")
@click.option("--confidence", default=0.8, type=float)
def log_insight(
    store: str, title: str, summary_text: str, study: str, researcher: str,
    study_date: str, tags: str, evidence: str, confidence: float,
) -> None:
    """Add a new research insight to the ledger."""
    ledger = Ledger(store_path=store)
    ins = Insight(
        title=title, summary=summary_text, study_name=study, study_date=study_date,
        researcher=researcher, tags=[t.strip() for t in tags.split(",") if t.strip()],
        raw_evidence=evidence, confidence=confidence,
    )
    ledger.add_insight(ins)
    console.print(f"[green]✓[/green] Insight logged: [bold]{ins.id}[/bold] — {ins.title}")


# ── log-decision ──────────────────────────────────────────────────────────────

@cli.command("log-decision")
@click.option("--store", required=True)
@click.option("--title", prompt=True)
@click.option("--description", "desc", prompt=True)
@click.option("--type", "dtype", default="feature", type=click.Choice([d.value for d in DecisionType]))
@click.option("--owner", prompt=True)
@click.option("--team", prompt=True)
@click.option("--reference", default="", help="Doc URL, spec title, brief ID — free form")
@click.option("--date", "dec_date", default=str(date.today()))
def log_decision(
    store: str, title: str, desc: str, dtype: str, owner: str,
    team: str, reference: str, dec_date: str,
) -> None:
    """Add a new product decision to the ledger."""
    ledger = Ledger(store_path=store)
    dec = Decision(
        title=title, description=desc, decision_type=dtype, owner=owner,
        team=team, reference=reference, decision_date=dec_date,
    )
    ledger.add_decision(dec)
    console.print(f"[green]✓[/green] Decision logged: [bold]{dec.id}[/bold] — {dec.title}")


# ── link ──────────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--store", required=True)
@click.option("--insight-id", required=True)
@click.option("--decision-id", required=True)
@click.option("--status", default="adopted", type=click.Choice([s.value for s in LinkStatus if s != LinkStatus.PROPOSED]))
@click.option("--strength", default="high", type=click.Choice([s.value for s in LinkStrength]))
@click.option("--rationale", default="")
@click.option("--logged-by", default="")
@click.option("--llm/--no-llm", default=True)
@click.option("--backend", default=None)
def link(
    store: str, insight_id: str, decision_id: str, status: str, strength: str,
    rationale: str, logged_by: str, llm: bool, backend: Optional[str],
) -> None:
    """Manually log a research insight→decision link."""
    from .llm import generate_link_note

    ledger = Ledger(store_path=store)
    ins = ledger.get_insight(insight_id)
    dec = ledger.get_decision(decision_id)
    if not ins:
        console.print(f"[red]Insight not found:[/red] {insight_id}")
        sys.exit(1)
    if not dec:
        console.print(f"[red]Decision not found:[/red] {decision_id}")
        sys.exit(1)

    lk = InsightLink(
        insight_id=insight_id, decision_id=decision_id, status=status,
        strength=strength, rationale=rationale, logged_by=logged_by,
        logged_date=str(date.today()),
    )

    if llm:
        backends = available_backends()
        chosen = backend or (backends[0] if backends else None)
        if chosen:
            lk.llm_note = generate_link_note(ins, dec, lk, backend=chosen)

    ledger.add_link(lk)
    console.print(f"[green]✓[/green] Link created: [bold]{lk.id}[/bold]")
    if lk.llm_note:
        console.print(f"[dim]LLM note:[/dim] {lk.llm_note}")


# ── propose ───────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--store", required=True)
@click.option("--top", default=5, show_default=True, help="Max proposals to generate")
@click.option("--threshold", default=0.5, show_default=True, type=float, help="Min confidence (0–1)")
@click.option("--backend", default=None)
@click.option("--json-output", is_flag=True)
def propose(
    store: str, top: int, threshold: float, backend: Optional[str], json_output: bool,
) -> None:
    """
    Auto-propose insight→decision links using a single LLM call.

    Proposed links are stored with status='proposed' and excluded from
    activation rate until confirmed via the `review` command.
    """
    ledger = Ledger(store_path=store)
    backends = available_backends()
    chosen = backend or (backends[0] if backends else None)
    if not chosen:
        console.print("[red]No LLM backend available. Set ANTHROPIC_API_KEY, GEMINI_API_KEY or OPENAI_API_KEY.[/red]")
        sys.exit(1)

    console.print(f"[dim]Running auto-proposal via {chosen} (top={top}, threshold={threshold})…[/dim]")
    proposals = propose_links(ledger, top_k=top, threshold=threshold, backend=chosen)

    if not proposals:
        console.print("[yellow]No proposals above the confidence threshold.[/yellow]")
        return

    for lk in proposals:
        ledger.add_link(lk)

    if json_output:
        click.echo(json.dumps([lk.to_dict() for lk in proposals], indent=2))
        return

    table = Table(box=box.SIMPLE_HEAVY, header_style="bold magenta")
    table.add_column("Insight", max_width=34)
    table.add_column("Decision", max_width=28)
    table.add_column("Conf", width=6)
    table.add_column("Rationale", max_width=40)

    for lk in proposals:
        ins = ledger.get_insight(lk.insight_id)
        dec = ledger.get_decision(lk.decision_id)
        table.add_row(
            ins.title[:34] if ins else lk.insight_id,
            dec.title[:28] if dec else lk.decision_id,
            f"{lk.proposal_confidence:.2f}",
            lk.rationale[:40],
        )
    console.print(table)
    console.print(f"\n[magenta]{len(proposals)} proposal(s) stored.[/magenta] Run [bold]insight-ledger review --store {store}[/bold] to arbitrate.")


# ── review ────────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--store", required=True)
@click.option("--json-output", is_flag=True)
def review(store: str, json_output: bool) -> None:
    """
    Interactive review queue for auto-proposed links.

    For each proposal: (a)dopt · (p)artial · (d)ecline · (e)efer · (s)kip
    Confirmed links are removed from the proposal queue and added to the ledger.
    """
    ledger = Ledger(store_path=store)
    proposals = resolve_proposals(ledger)

    if not proposals:
        console.print("[dim]No proposed links awaiting review.[/dim]")
        return

    if json_output:
        click.echo(json.dumps([r.to_dict() for r in proposals], indent=2))
        return

    console.print(Panel(
        f"[bold]{len(proposals)} proposed link(s) awaiting arbitration[/bold]\n"
        "[dim](a)dopt  (p)artial  (d)ecline  (e)defer  (s)kip[/dim]",
        border_style="magenta",
    ))

    accepted = declined = skipped = 0

    for r in proposals:
        console.print(f"\n[bold magenta]PROPOSAL[/bold magenta] conf={r.link.proposal_confidence:.2f}")
        console.print(f"  [cyan]Insight:[/cyan] {r.insight.title}")
        console.print(f"  [cyan]Study:[/cyan] {r.insight.study_name} ({r.insight.study_date or '—'})")
        console.print(f"  [cyan]Decision:[/cyan] {r.decision.title} [{r.decision.decision_type}]")
        console.print(f"  [cyan]LLM rationale:[/cyan] {r.link.rationale}")

        choice = click.prompt(
            "  Action",
            type=click.Choice(["a", "p", "d", "e", "s"], case_sensitive=False),
            default="s",
        )

        if choice == "s":
            skipped += 1
            continue

        if choice in ("a", "p", "e"):
            strength_choice = click.prompt(
                "  Strength",
                type=click.Choice(["high", "medium", "low"], case_sensitive=False),
                default="medium",
            )
            rationale_override = click.prompt("  Your rationale (Enter to keep LLM's)", default="")
        else:
            strength_choice = r.link.strength
            rationale_override = ""

        status_map = {"a": "adopted", "p": "partial", "d": "declined", "e": "deferred"}
        r.link.status = status_map[choice]
        r.link.strength = strength_choice if choice in ("a", "p", "e") else r.link.strength
        r.link.auto_proposed = True   # preserve provenance
        if rationale_override.strip():
            r.link.rationale = rationale_override.strip()

        ledger.links[r.link.id] = r.link
        ledger._save()

        if choice in ("a", "p"):
            accepted += 1
            console.print(f"  [green]✓ Confirmed as {r.link.status}[/green]")
        elif choice == "d":
            declined += 1
            console.print("  [red]✗ Declined[/red]")
        else:
            console.print("  [cyan]→ Deferred[/cyan]")

    console.print(f"\n[dim]Review complete: {accepted} confirmed, {declined} declined, {skipped} skipped.[/dim]")


# ── ranked ────────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--store", default=None)
@click.option("--demo", is_flag=True)
@click.option("--json-output", is_flag=True)
def ranked(store: Optional[str], demo: bool, json_output: bool) -> None:
    """Show insights ranked by influence score (confirmed links only)."""
    ledger = _make_ledger(store, demo)
    results = ranked_insights(ledger)

    if json_output:
        click.echo(json.dumps(
            [{"insight": ins.to_dict(), "influence_score": score} for ins, score in results],
            indent=2,
        ))
        return

    table = Table(box=box.SIMPLE_HEAVY, header_style=f"bold {ACCENT}")
    table.add_column("Rank", width=5)
    table.add_column("Insight", max_width=40)
    table.add_column("Score", width=9)
    table.add_column("Researcher", max_width=18)
    table.add_column("Study", max_width=26)

    for i, (ins, score) in enumerate(results, 1):
        bar = "█" * int(score * 5) + "░" * (5 - int(score * 5))
        table.add_row(str(i), ins.title[:40], f"{score:.2f} {bar}",
                      ins.researcher or "—", ins.study_name[:26] or "—")
    console.print(table)


# ── export ────────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--store", default=None)
@click.option("--demo", is_flag=True)
@click.option("--out", default=None)
def export(store: Optional[str], demo: bool, out: Optional[str]) -> None:
    """Export full ledger (including proposals) to JSON."""
    ledger = _make_ledger(store, demo)
    text = json.dumps(ledger.export_json(), indent=2)
    if out:
        Path(out).write_text(text)
        console.print(f"[green]✓[/green] Exported to {out}")
    else:
        click.echo(text)


# ── demo ──────────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--json-output", is_flag=True)
def demo(json_output: bool) -> None:
    """Load and summarise the built-in synthetic dataset.

    Note: all data is entirely fabricated for illustration.
    """
    ledger = load_synthetic_ledger()
    records = resolve_records(ledger)
    s = compute_summary(ledger, records)

    backends = available_backends()
    if backends:
        s.llm_narrative = generate_ledger_narrative(s, records, backend=backends[0])

    if json_output:
        click.echo(json.dumps(s.to_dict(), indent=2))
        return

    console.print(Panel(
        "[bold]insight-ledger · DEMO (synthetic data)[/bold]\n"
        "[dim]All insights, decisions and links are fabricated for illustration.[/dim]",
        border_style="yellow",
    ))
    t = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    t.add_column("k", style="dim")
    t.add_column("v", style="bold")
    for label, val in [
        ("Insights", s.total_insights), ("Decisions", s.total_decisions),
        ("Confirmed links", s.total_links),
        ("Awaiting arbitration", f"[magenta]{s.proposed_count}[/magenta]"),
        ("Activation rate", f"{s.activation_rate * 100:.0f}%"),
        ("Adopted", s.adopted), ("Partial", s.partial),
        ("Declined", s.declined), ("Deferred", s.deferred),
    ]:
        t.add_row(label, str(val))
    console.print(t)
    if s.llm_narrative:
        console.print(Panel(s.llm_narrative, title="[dim]narrative[/dim]", border_style="dim"))


if __name__ == "__main__":
    cli()
