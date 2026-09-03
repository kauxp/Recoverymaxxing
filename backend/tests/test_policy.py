from app.models import ActionType, EventStatus
from app.services.policy import decide


def test_global_attempt_cap_overrides_category_policy():
    decision = decide("INSUFFICIENT_FUNDS", attempt_count=3)
    assert decision.terminal is True
    assert decision.action == ActionType.ESCALATE_HUMAN
    assert decision.terminal_status == EventStatus.ESCALATED


def test_insufficient_funds_retries_with_backoff():
    decision = decide("INSUFFICIENT_FUNDS", attempt_count=0)
    assert decision.action == ActionType.RETRY_CHARGE
    assert decision.terminal is False


def test_risk_declined_never_retries_same_instrument():
    decision = decide("RISK_DECLINED", attempt_count=0)
    assert decision.action == ActionType.NO_ACTION_RISK_BLOCK
    assert decision.terminal is True
    assert decision.terminal_status == EventStatus.ESCALATED


def test_risk_declined_stays_terminal_regardless_of_attempt_count():
    for attempt_count in (0, 1, 2):
        decision = decide("RISK_DECLINED", attempt_count=attempt_count)
        assert decision.action == ActionType.NO_ACTION_RISK_BLOCK
        assert decision.terminal is True


def test_subscription_halted_escalates_with_zero_automated_attempts():
    decision = decide("SUBSCRIPTION_HALTED", attempt_count=0)
    assert decision.action == ActionType.ESCALATE_HUMAN
    assert decision.terminal is True
    assert decision.terminal_status == EventStatus.ESCALATED


def test_abandoned_checkout_sends_two_reminders_then_marks_unrecoverable():
    first = decide("ABANDONED_CHECKOUT", attempt_count=0)
    assert first.action == ActionType.RESEND_LINK
    assert first.terminal is False

    second = decide("ABANDONED_CHECKOUT", attempt_count=1)
    assert second.action == ActionType.RESEND_LINK
    assert second.terminal is False

    third = decide("ABANDONED_CHECKOUT", attempt_count=2)
    assert third.action == ActionType.NO_ACTION_RISK_BLOCK
    assert third.terminal is True
    assert third.terminal_status == EventStatus.UNRECOVERABLE


def test_customer_action_needed_sends_link_then_resend_then_escalates():
    first = decide("CUSTOMER_ACTION_NEEDED", attempt_count=0)
    assert first.action == ActionType.SEND_PAYMENT_LINK
    assert first.terminal is False

    second = decide("CUSTOMER_ACTION_NEEDED", attempt_count=1)
    assert second.action == ActionType.RESEND_LINK
    assert second.terminal is False

    third = decide("CUSTOMER_ACTION_NEEDED", attempt_count=2)
    assert third.action == ActionType.ESCALATE_HUMAN
    assert third.terminal is True
    assert third.terminal_status == EventStatus.ESCALATED


def test_unmapped_category_escalates_without_guessing():
    decision = decide("UNMAPPED", attempt_count=0)
    assert decision.action == ActionType.ESCALATE_HUMAN
    assert decision.terminal is True
