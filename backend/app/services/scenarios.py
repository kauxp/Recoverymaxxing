from datetime import datetime, timezone

from app.config import settings
from app.models import Batch, RecoveryEvent, SourceType
from app.services import razorpay_client

SCENARIOS = [
    {
        "name": "SaaS subscriber, card expired mid-cycle",
        "narrative": (
            "A ₹999/month SaaS subscriber's card expired between billing cycles — "
            "extremely common, the customer isn't even aware yet."
        ),
        "source_type": SourceType.SUBSCRIPTION_CHARGE,
        "error_code": "BAD_REQUEST_ERROR",
        "error_reason": "card_expired",
        "amount_paise": 99900,
        "is_genuine": True,
        "expected_category": "CUSTOMER_ACTION_NEEDED",
        "acceptance_criteria": "Must NOT blind-retry the expired card. Should send a fresh payment link, escalate only after one resend goes unpaid.",
    },
    {
        "name": "EMI-style mandate, month-end insufficient funds",
        "narrative": (
            "A recurring ₹2,499 EMI mandate fails on the 28th because the customer's "
            "salary hasn't landed yet — a textbook case where a short retry after payday recovers real money."
        ),
        "source_type": SourceType.SUBSCRIPTION_CHARGE,
        "error_code": "BAD_REQUEST_ERROR",
        "error_reason": "insufficient_funds",
        "amount_paise": 249900,
        "is_genuine": False,
        "expected_category": "INSUFFICIENT_FUNDS",
        "acceptance_criteria": "Should retry the same instrument with backoff (funds may simply replenish) rather than giving up or escalating immediately.",
    },
    {
        "name": "High-ticket electronics purchase, issuer risk decline",
        "narrative": (
            "A customer trying to pay ₹48,500 for a laptop gets a generic issuer decline — "
            "the bank's own fraud engine flagged it, not a funds/detail problem."
        ),
        "source_type": SourceType.ORDER_CHECKOUT,
        "error_code": "GATEWAY_ERROR",
        "error_reason": "card_declined",
        "amount_paise": 4850000,
        "is_genuine": False,
        "expected_category": "RISK_DECLINED",
        "acceptance_criteria": "Must NEVER retry the same instrument — repeat attempts on an issuer risk decline can get the merchant's own MID flagged. Escalate immediately, zero retries.",
    },
    {
        "name": "Flash-sale traffic spike, bank auth timeout",
        "narrative": (
            "During a sale, the issuing bank's 3DS server times out under load for a ₹3,199 order — "
            "purely infrastructural, nothing wrong with the customer's money or card."
        ),
        "source_type": SourceType.ORDER_CHECKOUT,
        "error_code": "GATEWAY_ERROR",
        "error_reason": "payment_timed_out",
        "amount_paise": 319900,
        "is_genuine": False,
        "expected_category": "TRANSIENT_GATEWAY",
        "acceptance_criteria": "Should retry quickly (short backoff) — this is the most recoverable failure class and should not need customer involvement at all.",
    },
    {
        "name": "Distracted customer, OTP mistyped at checkout",
        "narrative": (
            "A customer fat-fingers their 3DS OTP while checking out for ₹2,150 worth of groceries, "
            "gets rushed by a delivery notification, and doesn't retry themselves."
        ),
        "source_type": SourceType.ORDER_CHECKOUT,
        "error_code": "BAD_REQUEST_ERROR",
        "error_reason": "incorrect_otp",
        "amount_paise": 215000,
        "is_genuine": False,
        "expected_category": "CUSTOMER_ACTION_NEEDED",
        "acceptance_criteria": "Needs a fresh OTP flow (new link), not a blind retry with the same stale session.",
    },
    {
        "name": "B2B annual invoice, payment link ignored",
        "narrative": (
            "A ₹85,000 annual-plan invoice sent as a payment link sits unopened for a week — "
            "the customer's accounts-payable team is just slow, not refusing to pay."
        ),
        "source_type": SourceType.PAYMENT_LINK,
        "error_code": None,
        "error_reason": "checkout_abandoned",
        "amount_paise": 8500000,
        "is_genuine": True,
        "expected_category": "ABANDONED_CHECKOUT",
        "acceptance_criteria": "Should send a reminder (cheap, low-risk), and if still unpaid after one reminder, close it out as unrecoverable rather than escalating a routine AP delay to a human.",
    },
    {
        "name": "Long-term subscriber, mandate already halted by Razorpay",
        "narrative": (
            "A ₹599/month subscriber's mandate has already failed 4 times natively and Razorpay itself "
            "halted the subscription — likely a job loss or card cancellation, a human win-back conversation is needed."
        ),
        "source_type": SourceType.SUBSCRIPTION_CHARGE,
        "error_code": None,
        "error_reason": "subscription_halted",
        "amount_paise": 59900,
        "is_genuine": False,
        "expected_category": "SUBSCRIPTION_HALTED",
        "acceptance_criteria": "Zero further automated attempts — Razorpay already exhausted native retries. Escalate straight to a human, don't pretend automation can still fix this.",
    },
    {
        "name": "Corporate card, daily transaction limit exceeded",
        "narrative": (
            "An employee tries to expense a ₹22,000 conference ticket on a corporate card and hits "
            "the card's daily transaction limit — resolves itself the next day, not a decline of the purchase itself."
        ),
        "source_type": SourceType.ORDER_CHECKOUT,
        "error_code": "BAD_REQUEST_ERROR",
        "error_reason": "transaction_limit_exceeded",
        "amount_paise": 2200000,
        "is_genuine": False,
        "expected_category": "LIMIT_EXCEEDED",
        "acceptance_criteria": "One retry after the limit window resets is reasonable; should not retry indefinitely or escalate on the very first failure.",
    },
    {
        "name": "Adversarial: unrecognized decline reason from a new acquiring bank",
        "narrative": (
            "A newly-onboarded acquiring bank returns a decline reason string the system has never seen: "
            "'risk_engine_geo_mismatch'. This tests whether the system guesses or admits it doesn't know."
        ),
        "source_type": SourceType.ORDER_CHECKOUT,
        "error_code": "GATEWAY_ERROR",
        "error_reason": "risk_engine_geo_mismatch",
        "amount_paise": 599900,
        "is_genuine": False,
        "expected_category": "UNMAPPED",
        "acceptance_criteria": "Must escalate rather than guess at a category it doesn't recognize — silently misclassifying an unknown reason is worse than admitting it doesn't know.",
    },
]


def load_scenarios(session, batch_name: str = "real-world-scenario-eval") -> Batch:
    now = datetime.now(timezone.utc)
    batch = Batch(name=batch_name, started_at=now, total_events=len(SCENARIOS))
    session.add(batch)
    session.flush()

    total_at_risk = 0
    for i, scenario in enumerate(SCENARIOS):
        is_genuine = scenario["is_genuine"]
        phone = "9000000000"
        if i == 0 and settings.DEMO_PHONE_NUMBER:
            phone = settings.DEMO_PHONE_NUMBER

        entity_id = f"sim_scenario_{i}"
        if is_genuine:
            result = razorpay_client.create_order(scenario["amount_paise"], receipt=f"scenario-{i}")
            if result["ok"]:
                entity_id = result["ref"]
            else:
                is_genuine = False

        event = RecoveryEvent(
            batch_id=batch.id,
            source_type=scenario["source_type"],
            razorpay_entity_id=entity_id,
            customer_name=scenario["name"],
            customer_email=f"scenario{i}@example.com",
            customer_phone=phone,
            amount_paise=scenario["amount_paise"],
            original_error_code=scenario["error_code"],
            original_error_reason=scenario["error_reason"],
            is_genuine=is_genuine,
            created_at=now,
            updated_at=now,
        )
        session.add(event)
        total_at_risk += scenario["amount_paise"]

    batch.total_amount_at_risk_paise = total_at_risk
    session.add(batch)
    session.commit()
    session.refresh(batch)
    return batch
