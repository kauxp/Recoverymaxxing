from datetime import datetime, timezone

import pytest
from sqlmodel import Session, SQLModel, create_engine

from app import models
from app.services import actions, razorpay_client
from app.services.policy import RecoveryDecision


@pytest.fixture
def session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def _make_event(session, phone: str) -> models.RecoveryEvent:
    now = datetime.now(timezone.utc)
    batch = models.Batch(name="test-batch", started_at=now)
    session.add(batch)
    session.flush()

    event = models.RecoveryEvent(
        batch_id=batch.id,
        source_type=models.SourceType.PAYMENT_LINK,
        razorpay_entity_id="sim_x",
        customer_name="Test User",
        customer_email="test@example.com",
        customer_phone=phone,
        amount_paise=10000,
        original_error_code="BAD_REQUEST_ERROR",
        original_error_reason="card_expired",
        root_cause_category="CUSTOMER_ACTION_NEEDED",
        is_genuine=True,
        created_at=now,
        updated_at=now,
    )
    session.add(event)
    session.commit()
    session.refresh(event)
    return event


def _send_link_decision() -> RecoveryDecision:
    return RecoveryDecision(
        action=models.ActionType.SEND_PAYMENT_LINK,
        next_delay_seconds=0,
        terminal=False,
        reason="test",
        rule_fired="TEST_RULE",
    )


def test_real_notification_only_sent_to_configured_demo_phone(session, monkeypatch):
    monkeypatch.setattr(actions.settings, "DEMO_PHONE_NUMBER", "9999999999")
    monkeypatch.setattr(actions.settings, "NOTIFY_WHATSAPP", False)

    captured = {}

    def fake_create_payment_link(**kwargs):
        captured["notify"] = kwargs.get("notify")
        return {"ok": True, "ref": "plink_fake"}

    monkeypatch.setattr(razorpay_client, "create_payment_link", fake_create_payment_link)

    event = _make_event(session, phone="9999999999")
    attempt = actions.execute(session, event, _send_link_decision())

    assert captured["notify"] == {"sms": True, "whatsapp": False}
    assert attempt.real_notification_sent is True


def test_no_real_notification_for_a_non_demo_phone(session, monkeypatch):
    monkeypatch.setattr(actions.settings, "DEMO_PHONE_NUMBER", "9999999999")

    captured = {}

    def fake_create_payment_link(**kwargs):
        captured["notify"] = kwargs.get("notify")
        return {"ok": True, "ref": "plink_fake"}

    monkeypatch.setattr(razorpay_client, "create_payment_link", fake_create_payment_link)

    event = _make_event(session, phone="8888888888")
    actions.execute(session, event, _send_link_decision())

    assert captured["notify"] == {"sms": False, "email": False}


def test_no_real_notification_when_demo_phone_not_configured(session, monkeypatch):
    monkeypatch.setattr(actions.settings, "DEMO_PHONE_NUMBER", "")

    captured = {}

    def fake_create_payment_link(**kwargs):
        captured["notify"] = kwargs.get("notify")
        return {"ok": True, "ref": "plink_fake"}

    monkeypatch.setattr(razorpay_client, "create_payment_link", fake_create_payment_link)

    event = _make_event(session, phone="9999999999")
    actions.execute(session, event, _send_link_decision())

    assert captured["notify"] == {"sms": False, "email": False}
