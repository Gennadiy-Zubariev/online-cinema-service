from fastapi import APIRouter

from src.accounts.dependencies import CurrentUser
from src.database.session import DbSession
from src.payments.schemas import CheckoutResponse
from src.payments.service import start_checkout

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
