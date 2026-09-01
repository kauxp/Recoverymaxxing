import random
import uuid
from datetime import datetime, timezone

from app.config import settings
from app.models import Batch, RecoveryEvent, SourceType
from app.services import razorpay_client

FAILURE_TEMPLATES = [
    ("BAD_REQUEST_ERROR", "insufficient_funds", SourceType.SUBSCRIPTION_CHARGE),
    ("GATEWAY_ERROR", "gateway_technical_error", SourceType.ORDER_CHECKOUT),
    ("GATEWAY_ERROR", "issuer_technical_error", SourceType.ORDER_CHECKOUT),
    ("BAD_REQUEST_ERROR", "payment_timed_out", SourceType.ORDER_CHECKOUT),
    ("BAD_REQUEST_ERROR", "transaction_limit_exceeded", SourceType.SUBSCRIPTION_CHARGE),
    ("BAD_REQUEST_ERROR", "card_expired", SourceType.SUBSCRIPTION_CHARGE),
    ("BAD_REQUEST_ERROR", "incorrect_otp", SourceType.PAYMENT_LINK),
    ("GATEWAY_ERROR", "authentication_failed", SourceType.PAYMENT_LINK),
    ("GATEWAY_ERROR", "card_declined", SourceType.ORDER_CHECKOUT),
    (None, "checkout_abandoned", SourceType.PAYMENT_LINK),
    (None, "subscription_halted", SourceType.SUBSCRIPTION_CHARGE),
]

FIRST_NAMES = ["Aarav", "Priya", "Rohan", "Sneha", "Vikram", "Ananya", "Karan", "Meera", "Arjun", "Divya"]
LAST_NAMES = ["Sharma", "Patel", "Nair", "Iyer", "Gupta", "Reddy", "Singh", "Rao", "Menon", "Verma"]


def _fake_customer(rng: random.Random) -> dict:
    name = f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}"
    slug = name.lower().replace(" ", ".")
    return {
        "name": name,
        "email": f"{slug}.{rng.randint(1, 9999)}@example.com",
        "phone": f"9{rng.randint(100000000, 999999999)}",
    }


def generate_batch(
    session,
    name: str,
    n_events: int = 30,
    n_genuine_api_calls: int = 10,
    seed: int = 42,
) -> Batch:
    rng = random.Random(seed)
    now = datetime.now(timezone.utc)

    batch = Batch(name=name, started_at=now, total_events=n_events)
    session.add(batch)
    session.flush()

    LINK_SENDING_REASONS = {
        "insufficient_funds", "gateway_technical_error", "issuer_technical_error",
        "payment_timed_out", "transaction_limit_exceeded", "card_expired",
        "incorrect_otp", "authentication_failed", "checkout_abandoned",
    }
    demo_phone_assigned = False

    total_at_risk = 0
    for i in range(n_events):
        code, reason, source_type = rng.choice(FAILURE_TEMPLATES)
        customer = _fake_customer(rng)
        amount_paise = rng.randint(29900, 499900)

        is_demo_notification_target = (
            not demo_phone_assigned and settings.DEMO_PHONE_NUMBER and reason in LINK_SENDING_REASONS
        )
        if is_demo_notification_target:
            customer["phone"] = settings.DEMO_PHONE_NUMBER
            demo_phone_assigned = True

        is_genuine = is_demo_notification_target or i < n_genuine_api_calls
        entity_id = f"sim_{uuid.uuid4().hex[:14]}"
        if is_genuine:
            result = razorpay_client.create_order(amount_paise, receipt=f"recovery-seed-{i}")
            if result["ok"]:
                entity_id = result["ref"]
            else:
                is_genuine = False

        event = RecoveryEvent(
            batch_id=batch.id,
            source_type=source_type,
            razorpay_entity_id=entity_id,
            customer_name=customer["name"],
            customer_email=customer["email"],
            customer_phone=customer["phone"],
            amount_paise=amount_paise,
            original_error_code=code,
            original_error_reason=reason,
            is_genuine=is_genuine,
            created_at=now,
            updated_at=now,
        )
        session.add(event)
        total_at_risk += amount_paise

    batch.total_amount_at_risk_paise = total_at_risk
    session.add(batch)
    session.commit()
    session.refresh(batch)
    return batch
