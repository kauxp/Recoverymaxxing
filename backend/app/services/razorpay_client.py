import razorpay

from app.config import settings

_client = None
_client_checked = False


def get_client():
    global _client, _client_checked
    if not _client_checked:
        _client_checked = True
        if settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_SECRET:
            _client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
    return _client


def create_order(amount_paise: int, currency: str = "INR", receipt: str = "") -> dict:
    client = get_client()
    if client is None:
        return {"ok": False, "error_code": "NO_CLIENT", "error_reason": "Razorpay keys not configured"}
    try:
        order = client.order.create({
            "amount": amount_paise,
            "currency": currency,
            "receipt": receipt,
        })
        return {"ok": True, "ref": order["id"], "raw": order}
    except Exception as exc:
        return {"ok": False, "error_code": type(exc).__name__, "error_reason": str(exc)}


def create_payment_link(
    amount_paise: int,
    description: str,
    customer: dict,
    currency: str = "INR",
    notify: dict | None = None,
) -> dict:
    client = get_client()
    if client is None:
        return {"ok": False, "error_code": "NO_CLIENT", "error_reason": "Razorpay keys not configured"}
    try:
        link = client.payment_link.create({
            "amount": amount_paise,
            "currency": currency,
            "description": description,
            "customer": customer,
            "notify": notify or {"sms": False, "email": False},
        })
        return {"ok": True, "ref": link["id"], "raw": link}
    except Exception as exc:
        return {"ok": False, "error_code": type(exc).__name__, "error_reason": str(exc)}


def fetch_payment(payment_id: str) -> dict:
    client = get_client()
    if client is None:
        return {"ok": False, "error_code": "NO_CLIENT", "error_reason": "Razorpay keys not configured"}
    try:
        payment = client.payment.fetch(payment_id)
        return {"ok": True, "raw": payment}
    except Exception as exc:
        return {"ok": False, "error_code": type(exc).__name__, "error_reason": str(exc)}
