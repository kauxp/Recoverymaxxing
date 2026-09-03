from app.services.diagnosis import diagnose


def test_insufficient_funds():
    assert diagnose("BAD_REQUEST_ERROR", "insufficient_funds") == "INSUFFICIENT_FUNDS"


def test_transient_gateway_reasons():
    assert diagnose("GATEWAY_ERROR", "gateway_technical_error") == "TRANSIENT_GATEWAY"
    assert diagnose("GATEWAY_ERROR", "issuer_technical_error") == "TRANSIENT_GATEWAY"
    assert diagnose("BAD_REQUEST_ERROR", "payment_timed_out") == "TRANSIENT_GATEWAY"


def test_limit_exceeded_reasons():
    assert diagnose("BAD_REQUEST_ERROR", "transaction_limit_exceeded") == "LIMIT_EXCEEDED"
    assert diagnose("BAD_REQUEST_ERROR", "transaction_daily_limit_exceeded") == "LIMIT_EXCEEDED"


def test_customer_action_needed_reasons():
    for reason in ["card_expired", "incorrect_card_details", "incorrect_cvv", "incorrect_otp", "otp_expired"]:
        assert diagnose("BAD_REQUEST_ERROR", reason) == "CUSTOMER_ACTION_NEEDED"


def test_auth_failed():
    assert diagnose("GATEWAY_ERROR", "authentication_failed") == "AUTH_FAILED"


def test_risk_declined():
    assert diagnose("GATEWAY_ERROR", "card_declined") == "RISK_DECLINED"


def test_unknown_reason_is_unmapped_not_guessed():
    assert diagnose("SOME_ERROR", "totally_unknown_reason") == "UNMAPPED"


def test_abandoned_checkout_sentinel():
    assert diagnose(None, "checkout_abandoned") == "ABANDONED_CHECKOUT"


def test_subscription_halted_sentinel():
    assert diagnose(None, "subscription_halted") == "SUBSCRIPTION_HALTED"


def test_diagnosis_is_case_insensitive():
    assert diagnose("BAD_REQUEST_ERROR", "INSUFFICIENT_FUNDS") == "INSUFFICIENT_FUNDS"
