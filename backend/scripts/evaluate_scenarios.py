import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rich.console import Console
from sqlmodel import select

from app.db import create_db_and_tables, get_session
from app.models import EventStatus, RecoveryAttempt, RecoveryEvent
from app.services.orchestrator import RecoveryOrchestrator
from app.services.scenarios import SCENARIOS, load_scenarios

console = Console(record=True)


def grade(scenario: dict, event: RecoveryEvent, attempts: list[RecoveryAttempt]) -> tuple[str, str]:
    category_ok = event.root_cause_category == scenario["expected_category"]
    attempt_summary = " -> ".join(f"{a.action_type}({a.outcome_status})" for a in attempts) or "no attempts"

    if not category_ok:
        return (
            "FAIL",
            f"Expected category {scenario['expected_category']}, got {event.root_cause_category}. "
            f"Attempts: {attempt_summary}.",
        )

    if scenario["expected_category"] == "RISK_DECLINED":
        retried_same_instrument = any(a.action_type == "retry_charge" for a in attempts)
        if retried_same_instrument:
            return ("FAIL", "Retried a risk-declined instrument — this is the one rule that must never break.")
        return ("PASS", f"Correctly blocked with zero retries, final status={event.status}. Attempts: {attempt_summary}.")

    if scenario["expected_category"] == "SUBSCRIPTION_HALTED":
        if len(attempts) > 1 or event.status != EventStatus.ESCALATED:
            return ("FAIL", f"Expected an immediate single escalation, got {len(attempts)} attempts, status={event.status}.")
        return ("PASS", f"Escalated immediately with zero automated retry attempts, as expected. Attempts: {attempt_summary}.")

    if scenario["expected_category"] == "UNMAPPED":
        if event.status != EventStatus.ESCALATED:
            return ("FAIL", f"Expected escalation on an unrecognized reason, got status={event.status}.")
        return ("PASS", f"Correctly admitted it didn't recognize the reason and escalated instead of guessing. Attempts: {attempt_summary}.")

    if event.status not in (EventStatus.RECOVERED, EventStatus.ESCALATED, EventStatus.UNRECOVERABLE):
        return ("FAIL", f"Event never reached a terminal state: status={event.status}.")

    return (
        "PASS",
        f"Classified correctly, final status={event.status}. Attempts: {attempt_summary}.",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-llm", action="store_true", help="skip LLM explanations")
    args = parser.parse_args()

    create_db_and_tables()
    session = get_session()

    batch = load_scenarios(session)
    console.print(f"[bold]Loaded {len(SCENARIOS)} real-world scenarios into batch #{batch.id}[/bold]\n")

    orchestrator = RecoveryOrchestrator(use_llm=not args.no_llm)
    orchestrator.run_batch(session, batch.id)

    events = session.exec(select(RecoveryEvent).where(RecoveryEvent.batch_id == batch.id)).all()

    passed = 0
    total_at_risk_paise = 0
    total_recovered_paise = 0
    for scenario, event in zip(SCENARIOS, events):
        attempts = session.exec(
            select(RecoveryAttempt).where(RecoveryAttempt.event_id == event.id).order_by(RecoveryAttempt.attempt_number)
        ).all()
        verdict, note = grade(scenario, event, attempts)
        passed += verdict == "PASS"
        total_at_risk_paise += event.amount_paise
        total_recovered_paise += event.recovered_amount_paise

        color = "green" if verdict == "PASS" else "red"
        console.rule(f"[{color}]{verdict}[/{color}] — {scenario['name']}")
        console.print(f"[dim]Narrative:[/dim] {scenario['narrative']}")
        console.print(f"[dim]Acceptance criteria:[/dim] {scenario['acceptance_criteria']}")
        console.print(f"[dim]Outcome:[/dim] {note}")
        console.print(f"[dim]Amount:[/dim] Rs.{event.amount_paise / 100:,.2f}  "
                       f"[dim]Genuine Razorpay call:[/dim] {event.is_genuine}\n")

    console.rule("[bold]Summary[/bold]")
    console.print(f"{passed}/{len(SCENARIOS)} scenarios passed real-world evaluation.")
    rate = (total_recovered_paise / total_at_risk_paise * 100) if total_at_risk_paise else 0.0
    console.print(f"Rs.{total_recovered_paise / 100:,.2f} recovered of Rs.{total_at_risk_paise / 100:,.2f} at risk "
                   f"({rate:.1f}%) across these 9 named scenarios.")

    report_path = Path(__file__).resolve().parent.parent / "scenario_report.txt"
    report_path.write_text(console.export_text())
    console.print(f"[dim]Full report written to {report_path}[/dim]")


if __name__ == "__main__":
    main()
