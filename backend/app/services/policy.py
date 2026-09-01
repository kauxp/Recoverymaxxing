from dataclasses import dataclass
from typing import Optional

from app.models import ActionType, EventStatus

GLOBAL_MAX_ATTEMPTS = 3


@dataclass(frozen=True)
class Step:
    action: ActionType
    reason: str
    rule: str
    terminal: bool = False
    delay: int = 0
    terminal_status: Optional[EventStatus] = None


@dataclass
class RecoveryDecision:
    action: ActionType
    next_delay_seconds: int
    terminal: bool
    reason: str
    rule_fired: str
    terminal_status: Optional[EventStatus] = None


POLICY: dict[str, list[Step]] = {
    "INSUFFICIENT_FUNDS": [
        Step(ActionType.RETRY_CHARGE, "Insufficient funds; retry same instrument after backoff",
             "INSUFFICIENT_FUNDS_RETRY", delay=30),
    ],
    "TRANSIENT_GATEWAY": [
        Step(ActionType.RETRY_CHARGE, "Transient gateway/issuer failure; short retry",
             "TRANSIENT_GATEWAY_RETRY", delay=10),
    ],
    "LIMIT_EXCEEDED": [
        Step(ActionType.RETRY_CHARGE, "Transaction/daily limit exceeded; retry after the limit window",
             "LIMIT_EXCEEDED_RETRY", delay=60),
        Step(ActionType.ESCALATE_HUMAN, "Limit-exceeded retry already used once",
             "LIMIT_EXCEEDED_CAP", terminal=True, terminal_status=EventStatus.ESCALATED),
    ],
    "CUSTOMER_ACTION_NEEDED": [
        Step(ActionType.SEND_PAYMENT_LINK, "Customer must act; sending a fresh payment link instead of blind-retrying",
             "CUSTOMER_ACTION_NEEDED_NEW_LINK"),
        Step(ActionType.RESEND_LINK, "First link went unpaid; resending once more before giving up",
             "CUSTOMER_ACTION_NEEDED_RESEND", delay=90),
        Step(ActionType.ESCALATE_HUMAN, "Link sent and resent once with no completion",
             "CUSTOMER_ACTION_NEEDED_CAP", terminal=True, terminal_status=EventStatus.ESCALATED),
    ],
    "AUTH_FAILED": [
        Step(ActionType.SEND_PAYMENT_LINK, "Customer must act; sending a fresh payment link instead of blind-retrying",
             "AUTH_FAILED_NEW_LINK"),
        Step(ActionType.RESEND_LINK, "First link went unpaid; resending once more before giving up",
             "AUTH_FAILED_RESEND", delay=90),
        Step(ActionType.ESCALATE_HUMAN, "Link sent and resent once with no completion",
             "AUTH_FAILED_CAP", terminal=True, terminal_status=EventStatus.ESCALATED),
    ],
    "RISK_DECLINED": [
        Step(ActionType.NO_ACTION_RISK_BLOCK, "Risk decline — never retry same instrument; blocking further automated action",
             "RISK_DECLINED_NO_RETRY", terminal=True, terminal_status=EventStatus.ESCALATED),
    ],
    "SUBSCRIPTION_HALTED": [
        Step(ActionType.ESCALATE_HUMAN, "Razorpay already exhausted native retries and halted the subscription",
             "SUBSCRIPTION_HALTED_ESCALATE", terminal=True, terminal_status=EventStatus.ESCALATED),
    ],
    "ABANDONED_CHECKOUT": [
        Step(ActionType.RESEND_LINK, "Checkout abandoned; sending a first reminder",
             "ABANDONED_REMINDER_1", delay=5),
        Step(ActionType.RESEND_LINK, "First reminder went unanswered; sending one more before giving up",
             "ABANDONED_REMINDER_2", delay=15),
        Step(ActionType.NO_ACTION_RISK_BLOCK, "Two reminders sent with no completion; not worth escalating a low-value abandoned cart",
             "ABANDONED_CAP", terminal=True, terminal_status=EventStatus.UNRECOVERABLE),
    ],
    "UNMAPPED": [
        Step(ActionType.ESCALATE_HUMAN, "No safe automated recovery strategy for this category; escalating rather than guessing",
             "UNMAPPED_ESCALATE", terminal=True, terminal_status=EventStatus.ESCALATED),
    ],
}


def decide(category: str, attempt_count: int) -> RecoveryDecision:
    if attempt_count >= GLOBAL_MAX_ATTEMPTS:
        return RecoveryDecision(
            action=ActionType.ESCALATE_HUMAN,
            next_delay_seconds=0,
            terminal=True,
            reason="Global maximum attempt limit reached",
            rule_fired="GLOBAL_MAX_ATTEMPTS",
            terminal_status=EventStatus.ESCALATED,
        )

    steps = POLICY.get(category, POLICY["UNMAPPED"])
    step = steps[min(attempt_count, len(steps) - 1)]

    return RecoveryDecision(
        action=step.action,
        next_delay_seconds=step.delay,
        terminal=step.terminal,
        reason=step.reason,
        rule_fired=step.rule,
        terminal_status=step.terminal_status,
    )
