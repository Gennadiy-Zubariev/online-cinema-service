from typing import Annotated

from fastapi import APIRouter, Header, Request, status

from src.accounts.dependencies import CurrentUser
from src.database.session import DbSession
from src.payments.schemas import CheckoutResponse
from src.payments.service import start_checkout, process_webhook_event
from src.payments.stripe_client import parse_webhook_event

router = APIRouter(tags=["payments"])


@router.post("/orders/{order_id}/checkout", response_model=CheckoutResponse)
async def checkout_order(
    db: DbSession, current_user: CurrentUser, order_id: int
) -> CheckoutResponse:
    """Start paying for the current user's pending order via Stripe Checkout.

    Already purchased movies are removed from the order and the total is
    recalculated. Returns the Stripe page URL; the frontend redirects the user
    there. The payment result arrives later via the Stripe webhook.
    Returns 404 if the order does not exist or belongs to another user.
    Returns 409 if the order is not pending.
    Returns 400 if all movies of the order are already purchased
    (the order is canceled).
    """
    checkout_url = await start_checkout(
        db=db, user_id=current_user.id, order_id=order_id
    )
    return CheckoutResponse(checkout_url=checkout_url)


@router.post("/payments/webhook", status_code=status.HTTP_200_OK)
async def handle_stripe_webhook(
    db: DbSession,
    request: Request,
    stripe_signature: Annotated[str | None, Header()] = None,
) -> None:
    """Receive Stripe webhook events (called by Stripe, not by users).

    Verifies the Stripe-Signature header against the raw body. Handles
    checkout.session.completed (order paid, movies purchased) and
    checkout.session.expired (canceled payment); other events are ignored.
    Returns 400 if the signature is invalid or missing.
    """
    payload = await request.body()
    event = parse_webhook_event(payload, stripe_signature)
    await process_webhook_event(db, event)
