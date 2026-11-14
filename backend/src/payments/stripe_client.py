from stripe import StripeClient

from src.config.settings import get_settings
from src.orders.models import OrderItem

CURRENCY = "usd"

settings = get_settings()

stripe_client = StripeClient(settings.STRIPE_SECRET_KEY.get_secret_value())


def create_checkout_session(order_id: int, items: list[OrderItem]) -> str:
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
