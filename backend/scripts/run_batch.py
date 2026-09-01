import argparse
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rich.console import Console
from rich.table import Table
from sqlmodel import select

from app.db import create_db_and_tables, get_session
from app.models import Batch, EventStatus, RecoveryEvent
from app.schemas import BatchSummary, CategoryBreakdown
from app.services.orchestrator import RecoveryOrchestrator
from app.services.seed_data import generate_batch

console = Console(record=True)


def build_summary(session, batch: Batch) -> BatchSummary:
    events = session.exec(select(RecoveryEvent).where(RecoveryEvent.batch_id == batch.id)).all()

    per_category = defaultdict(lambda: {"total": 0, "recovered": 0, "at_risk": 0, "recovered_amount": 0})
    total_recovered = 0
    escalated = 0
    unrecoverable = 0
    genuine = 0

    for event in events:
        stats = per_category[event.root_cause_category]
        stats["total"] += 1
        stats["at_risk"] += event.amount_paise
        if event.status == EventStatus.RECOVERED:
            stats["recovered"] += 1
            stats["recovered_amount"] += event.recovered_amount_paise
            total_recovered += event.recovered_amount_paise
        elif event.status == EventStatus.ESCALATED:
            escalated += 1
        elif event.status == EventStatus.UNRECOVERABLE:
            unrecoverable += 1
        if event.is_genuine:
            genuine += 1

    by_category = [
        CategoryBreakdown(
            category=cat,
            total_events=s["total"],
            recovered_events=s["recovered"],
            recovery_rate_pct=(s["recovered"] / s["total"] * 100) if s["total"] else 0.0,
            amount_at_risk_paise=s["at_risk"],
            amount_recovered_paise=s["recovered_amount"],
        )
        for cat, s in sorted(per_category.items())
    ]

    return BatchSummary(
        batch_id=batch.id,
        batch_name=batch.name,
        total_events=len(events),
        genuine_events=genuine,
        simulated_events=len(events) - genuine,
        total_amount_at_risk_paise=batch.total_amount_at_risk_paise,
        total_recovered_paise=total_recovered,
        overall_recovery_rate_pct=(total_recovered / batch.total_amount_at_risk_paise * 100)
        if batch.total_amount_at_risk_paise else 0.0,
        escalated_count=escalated,
        unrecoverable_count=unrecoverable,
        by_category=by_category,
    ), events


def print_report(summary: BatchSummary, events: list[RecoveryEvent]) -> None:
    console.rule(f"[bold]Batch: {summary.batch_name} (#{summary.batch_id})[/bold]")

    console.print(f"Total events:          {summary.total_events}")
    console.print(f"  genuine API calls:   {summary.genuine_events}")
    console.print(f"  hand/simulated:      {summary.simulated_events}")
    console.print(f"Amount at risk:        Rs.{summary.total_amount_at_risk_paise / 100:,.2f}")
    console.print(f"Amount recovered:      Rs.{summary.total_recovered_paise / 100:,.2f}")
    console.print(f"Overall recovery rate: {summary.overall_recovery_rate_pct:.1f}%")
    console.print(f"Escalated to human:    {summary.escalated_count}")
    console.print(f"Unrecoverable:         {summary.unrecoverable_count}")

    table = Table(title="Recovery rate by root cause")
    table.add_column("Category")
    table.add_column("Events", justify="right")
    table.add_column("Recovered", justify="right")
    table.add_column("Rate", justify="right")
    table.add_column("Rs. at risk", justify="right")
    table.add_column("Rs. recovered", justify="right")

    for row in summary.by_category:
        table.add_row(
            row.category,
            str(row.total_events),
            str(row.recovered_events),
            f"{row.recovery_rate_pct:.0f}%",
            f"{row.amount_at_risk_paise / 100:,.2f}",
            f"{row.amount_recovered_paise / 100:,.2f}",
        )
    console.print(table)

    risk_declined = [e for e in events if e.root_cause_category == "RISK_DECLINED"]
    if risk_declined:
        e = risk_declined[0]
        console.rule("[bold yellow]Handled gracefully: a failure correctly NOT recovered[/bold yellow]")
        console.print(
            f"Event #{e.id} ({e.customer_name}, Rs.{e.amount_paise / 100:,.2f}) was classified "
            f"RISK_DECLINED. The policy engine refused to retry the same instrument, per the "
            f"never-retry-a-risk-decline rule, and escalated instead. Final status: {e.status}. "
            f"This is a correct non-recovery, not a bug."
        )

    unresolved_categories = {e.root_cause_category for e in events if e.status == EventStatus.UNRECOVERABLE}
    if unresolved_categories:
        console.print(f"\n[dim]Honest exception list — categories with unrecovered events: {sorted(unresolved_categories)}[/dim]")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--events", type=int, default=30, help="number of events to seed")
    parser.add_argument("--genuine", type=int, default=10, help="how many events attempt a real Razorpay test-mode API call")
    parser.add_argument("--no-llm", action="store_true", help="skip LLM explanations (rule engine still runs)")
    args = parser.parse_args()

    create_db_and_tables()
    session = get_session()

    batch = generate_batch(session, name="hackathon-demo-batch", n_events=args.events, n_genuine_api_calls=args.genuine)
    console.print(f"[green]Seeded batch #{batch.id} with {args.events} events "
                  f"({args.genuine} attempted real Razorpay test-mode calls).[/green]")

    orchestrator = RecoveryOrchestrator(use_llm=not args.no_llm)
    orchestrator.run_batch(session, batch.id)

    session.refresh(batch)
    summary, events = build_summary(session, batch)
    print_report(summary, events)

    report_path = Path(__file__).resolve().parent.parent / "report.txt"
    report_path.write_text(console.export_text())
    console.print(f"\n[dim]Full report written to {report_path}[/dim]")


if __name__ == "__main__":
    main()
