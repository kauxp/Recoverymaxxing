def diagnose(error_code: str, error_reason: str) -> str:

    reason = error_reason.lower()

    if reason == "insufficient_funds":
        return "INSUFFICIENT_FUNDS"

    if reason in {
        "gateway_technical_error",
        "issuer_technical_error",
        "payment_timed_out"
    }:
        return "TRANSIENT_GATEWAY"

    if reason in {
        "transaction_limit_exceeded",
        "transaction_daily_limit_exceeded"
    }:
        return "LIMIT_EXCEEDED"

    if reason in {
        "card_expired",
        "incorrect_card_details",
        "incorrect_cvv",
        "incorrect_otp",
        "otp_expired"
    }:
        return "CUSTOMER_ACTION_NEEDED"

    if reason == "authentication_failed":
        return "AUTH_FAILED"

    if reason == "card_declined":
        return "RISK_DECLINED"

    if reason == "checkout_abandoned":
        return "ABANDONED_CHECKOUT"

    if reason == "subscription_halted":
        return "SUBSCRIPTION_HALTED"

    return "UNMAPPED"