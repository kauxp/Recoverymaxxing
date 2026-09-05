import json
import random
from datetime import datetime, timezone

from app.models import (
    ActionType,
    Actor,
    AuditLogEntry,
    EventStatus,
    OutcomeStatus,
    RecoveryAttempt,
    RecoveryEvent,
    StepType,
)
from app.config import settings
from app.services.policy import RecoveryDecision
from app.services import razorpay_client

SIMULATED_RECOVERY_PROBABILITY = {
    "INSUFFICIENT_FUNDS": 0.45,
    "TRANSIENT_GATEWAY": 0.75,
    "LIMIT_EXCEEDED": 0.50,
    "CUSTOMER_ACTION_NEEDED": 0.55,
    "AUTH_FAILED": 0.50,
    "ABANDONED_CHECKOUT": 0.25,
    "RISK_DECLINED": 0.0,
    "SUBSCRIPTION_HALTED": 0.0,
    "UNMAPPED": 0.0,
}

ARTIFACT_ACTIONS = {ActionType.RETRY_CHARGE, ActionType.SEND_PAYMENT_LINK, ActionType.RESEND_LINK}


def execute(session, event: RecoveryEvent, decision: RecoveryDecision) -> RecoveryAttempt:
    now = datetime.now(timezone.utc)
    attempt_number = event.attempt_count + 1

    razorpay_ref = None
    api_error_code = None
    api_error_reason = None
    recovered_this_attempt = False

    send_real_notification = bool(settings.DEMO_PHONE_NUMBER) and event.customer_phone == settings.DEMO_PHONE_NUMBER
    notify = {"sms": True, "whatsapp": settings.NOTIFY_WHATSAPP} if send_real_notification else {"sms": False, "email": False}

    if decision.action in ARTIFACT_ACTIONS:
        if event.is_genuine:
            result = razorpay_client.create_payment_link(
                amount_paise=event.amount_paise,
                description=f"Recovery attempt {attempt_number} for {event.razorpay_entity_id}",
                customer={
                    "name": event.customer_name,
                    "email": event.customer_email,
                    "contact": event.customer_phone,
                },
                notify=notify,
            )
            if result["ok"]:
                razorpay_ref = result["ref"]
            else:
                api_error_code = result.get("error_code")
                api_error_reason = result.get("error_reason")
        else:
            razorpay_ref = f"sim_{event.id}_{attempt_number}"

        if not api_error_code:
            rng = random.Random(event.id * 1000 + attempt_number)
            probability = SIMULATED_RECOVERY_PROBABILITY.get(event.root_cause_category, 0.0)
            recovered_this_attempt = rng.random() < probability

    if decision.action not in ARTIFACT_ACTIONS:
        outcome_status = OutcomeStatus.SUCCESS
    elif api_error_code:
        outcome_status = OutcomeStatus.ERROR
    elif recovered_this_attempt:
        outcome_status = OutcomeStatus.SUCCESS
    else:
        outcome_status = OutcomeStatus.FAILED

    real_notification_sent = send_real_notification and decision.action in ARTIFACT_ACTIONS and not api_error_code
    notification_channels = None
    if real_notification_sent:
        channels = ["sms"] + (["whatsapp"] if settings.NOTIFY_WHATSAPP else [])
        notification_channels = ",".join(channels)

    attempt = RecoveryAttempt(
        event_id=event.id,
        attempt_number=attempt_number,
        action_type=decision.action,
        rule_fired=decision.rule_fired,
        razorpay_action_ref=razorpay_ref,
        outcome_status=outcome_status,
        outcome_code=api_error_code,
        outcome_reason=api_error_reason,
        backoff_seconds_used=decision.next_delay_seconds,
        real_notification_sent=real_notification_sent,
        notification_channels=notification_channels,
        created_at=now,
        resolved_at=now,
    )
    session.add(attempt)
    session.flush()

    session.add(AuditLogEntry(
        event_id=event.id,
        attempt_id=attempt.id,
        actor=Actor.SYSTEM,
        step_type=StepType.ACTION,
        message=(
            f"Executed {decision.action} (rule={decision.rule_fired}): {decision.reason}. "
            f"Outcome: {outcome_status}."
            + (f" Real notification requested via {notification_channels} to {event.customer_phone}"
               f" (Razorpay accepted the request; delivery is not confirmed by this API)."
               if real_notification_sent else "")
            + (f" Notification request FAILED: {api_error_reason}" if send_real_notification and api_error_code else "")
        ),
        payload_json=json.dumps({
            "razorpay_ref": razorpay_ref,
            "is_genuine": event.is_genuine,
            "api_error_code": api_error_code,
            "real_notification_sent": real_notification_sent,
            "notification_channels": notification_channels,
        }),
        created_at=now,
    ))

    event.attempt_count = attempt_number
    event.updated_at = now

    if recovered_this_attempt:
        event.status = EventStatus.RECOVERED
        event.recovered_amount_paise = event.amount_paise
        event.recovered_at = now
    elif decision.terminal:
        event.status = decision.terminal_status or EventStatus.ESCALATED
        session.add(AuditLogEntry(
            event_id=event.id,
            attempt_id=attempt.id,
            actor=Actor.SYSTEM,
            step_type=StepType.STOP_RULE_TRIGGERED,
            message=f"Stopping (rule={decision.rule_fired}): {decision.reason}. Final status: {event.status}.",
            payload_json="{}",
            created_at=now,
        ))
    else:
        event.status = EventStatus.RETRY_SCHEDULED
        event.next_action_at = now

    session.add(event)
    session.commit()
    return attempt
