from stripe import StripeClient, SignatureVerificationError, Event

from src.config.settings import get_settings
from src.orders.models import OrderItem
from src.payments.exceptions import InvalidWebhookError

CURRENCY = "usd"

settings = get_settings()

stripe_client = StripeClient(settings.STRIPE_SECRET_KEY.get_secret_value())


def create_checkout_session(order_id: int, items: list[OrderItem]) -> str:
    """Create a hosted Checkout Session for the items and return its URL.

    Prices come from price_at_order (price_data, no Stripe products); order_id
    goes to metadata and returns in the webhook. Sync network call: use
    run_in_threadpool. Raises RuntimeError if Stripe returns no URL.
    """
    session = stripe_client.v1.checkout.sessions.create(
        params={
            "mode": "payment",
            "line_items": [
                {
                    "quantity": 1,
                    "price_data": {
                        "currency": CURRENCY,
                        "unit_amount": int(item.price_at_order * 100),
                        "product_data": {"name": item.movie.name},
                    },
                }
                for item in items
            ],
            "metadata": {"order_id": str(order_id)},
            "success_url": (
                f"{settings.FRONTEND_URL}/payment/success"
                "?session_id={CHECKOUT_SESSION_ID}"
            ),
            "cancel_url": f"{settings.FRONTEND_URL}/payment/cancel",
        }
    )
    if session.url is None:
        raise RuntimeError("Stripe returned a checkout session without URL.")
    return session.url


def parse_webhook_event(payload: bytes, signature: str | None) -> Event:
    """Verify the Stripe-Signature header against the raw body and parse the event.

    Raises InvalidWebhookError for a missing / invalid signature, an old
    timestamp or a malformed payload. Local HMAC check, no network.
    """
    try:
        return stripe_client.construct_event(
            payload, signature, settings.STRIPE_WEBHOOK_SECRET.get_secret_value()
        )
    except (ValueError, SignatureVerificationError) as exc:
        raise InvalidWebhookError() from exc
