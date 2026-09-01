import json
from datetime import datetime, timezone

from sqlmodel import select

from app.models import Actor, AuditLogEntry, RecoveryEvent, StepType, TERMINAL_STATUSES
from app.services.actions import execute
from app.services.diagnosis import diagnose
from app.services.llm_explainer import LLMExplainer
from app.services.policy import decide


class RecoveryOrchestrator:
    def __init__(self, use_llm: bool = True):
        self.explainer = LLMExplainer() if use_llm else None

    def run_batch(self, session, batch_id: int) -> None:
        events = session.exec(
            select(RecoveryEvent).where(RecoveryEvent.batch_id == batch_id)
        ).all()
        for event in events:
            self._run_event_to_completion(session, event)

    def _run_event_to_completion(self, session, event: RecoveryEvent) -> None:
        guard = 0
        while event.status not in TERMINAL_STATUSES and guard < 10:
            self._process_step(session, event)
            guard += 1

    def _process_step(self, session, event: RecoveryEvent) -> None:
        now = datetime.now(timezone.utc)

        category = diagnose(event.original_error_code or "", event.original_error_reason or "")
        event.root_cause_category = category
        session.add(AuditLogEntry(
            event_id=event.id,
            actor=Actor.RULE_ENGINE,
            step_type=StepType.DIAGNOSIS,
            message=f"Classified as {category} from reason='{event.original_error_reason}'",
            payload_json=json.dumps({
                "error_code": event.original_error_code,
                "error_reason": event.original_error_reason,
            }),
            created_at=now,
        ))
        session.add(event)
        session.commit()

        decision = decide(category, event.attempt_count)
        session.add(AuditLogEntry(
            event_id=event.id,
            actor=Actor.RULE_ENGINE,
            step_type=StepType.DECISION,
            message=f"rule={decision.rule_fired} action={decision.action} terminal={decision.terminal}: {decision.reason}",
            payload_json=json.dumps({"attempt_count": event.attempt_count}),
            created_at=now,
        ))
        session.commit()

        attempt = execute(session, event, decision)

        if self.explainer is not None:
            try:
                explanation = self.explainer.explain({
                    "amount_inr": event.amount_paise / 100,
                    "error_reason": event.original_error_reason,
                    "category": category,
                    "action": str(decision.action),
                    "rule_fired": decision.rule_fired,
                    "reason": decision.reason,
                    "attempt_count": event.attempt_count,
                    "outcome": str(attempt.outcome_status),
                })
            except Exception as exc:
                explanation = f"(LLM explanation unavailable, falling back to the rule reason above: {exc})"

            session.add(AuditLogEntry(
                event_id=event.id,
                attempt_id=attempt.id,
                actor=Actor.LLM,
                step_type=StepType.LLM_EXPLANATION,
                message=explanation,
                payload_json="{}",
                created_at=datetime.now(timezone.utc),
            ))
            session.commit()
