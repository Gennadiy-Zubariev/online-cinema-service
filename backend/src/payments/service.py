import logging
from decimal import Decimal

from fastapi.concurrency import run_in_threadpool
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from stripe import Event

from src.accounts.models import User
from src.movies.models import PurchasedMovie
from src.movies.purchased_service import get_purchased_movie_ids
from src.orders.exceptions import (
    OrderMoviesPurchasedError,
    OrderNotFoundError,
    OrderNotPendingError,
)
from src.orders.models import Order, OrderItem, OrderStatusEnum
from src.payments.models import PaymentStatusEnum, Payment
from src.payments.stripe_client import create_checkout_session
from src.tasks.emails import send_payment_confirmation_email

logger = logging.getLogger(__name__)

CHECKOUT_COMPLETED = "checkout.session.completed"
CHECKOUT_EXPIRED = "checkout.session.expired"


async def _record_payment(
    db: AsyncSession,
    order: Order,
    session_id: str,
    amount: Decimal,
    status: PaymentStatusEnum,
) -> bool:
    """Insert a payment for a Stripe session; return False if already recorded.

    ON CONFLICT DO NOTHING on external_payment_id makes webhook redeliveries
    idempotent, also for concurrent deliveries. Does not commit.
    """
    payment_id = await db.scalar(
        insert(Payment)
        .values(
            user_id=order.user_id,
            order_id=order.id,
            status=status,
            amount=amount,
            external_payment_id=session_id,
        )
        .on_conflict_do_nothing(index_elements=["external_payment_id"])
        .returning(Payment.id)
    )
    return payment_id is not None


async def _complete_order_payment(
    db: AsyncSession, order_id: int, session_id: str, amount: Decimal
) -> None:
    """Record a successful payment, mark the order paid and grant its movies.

    Payment, status and purchased movies are written in one commit; the
    confirmation email is queued after it, only for a new payment.
    A missing or non-pending order is logged ("refund manually") instead of
    raising: money was charged, and a 5xx would only make Stripe retry.
    """
    order = await db.get(Order, order_id)
    if order is None:
        logger.error(
            "Stripe session %s was paid for missing order %s: refund manually.",
            session_id,
            order_id,
        )
        return

    is_new = await _record_payment(
        db, order, session_id, amount, PaymentStatusEnum.SUCCESSFUL
    )
    if not is_new:
        return

    if order.status != OrderStatusEnum.PENDING:
        logger.warning(
            "Order %s was %s when session %s was paid: refund manually.",
            order.id,
            order.status,
            session_id,
        )
    order.status = OrderStatusEnum.PAID

    movie_ids = await db.scalars(
        select(OrderItem.movie_id).where(OrderItem.order_id == order.id)
    )
    await db.execute(
        insert(PurchasedMovie)
        .values([{"user_id": order.user_id, "movie_id": m} for m in movie_ids])
        .on_conflict_do_nothing()
    )
    email = await db.scalar(select(User.email).where(User.id == order.user_id))
    await db.commit()
    send_payment_confirmation_email.delay(email, order.id, str(amount))


async def _cancel_order_payment(
    db: AsyncSession, order_id: int, session_id: str, amount: Decimal
) -> None:
    """Record a canceled payment for an expired session; the order stays pending.

    A missing order is ignored: no money was charged.
    """
    order = await db.get(Order, order_id)
    if order is None:
        return
    await _record_payment(db, order, session_id, amount, PaymentStatusEnum.CANCELED)
    await db.commit()


async def start_checkout(db: AsyncSession, user_id: int, order_id: int) -> str:
    """Create a Stripe Checkout Session for the user's pending order; return its URL.

    Raises OrderNotFoundError (also for another user's order) and
    OrderNotPendingError. Movies bought meanwhile are removed from the order
    and the total is recalculated; if all are bought, the order is canceled
    and committed before OrderMoviesPurchasedError is raised. Stripe is called
    after commit, so the network call does not hold the transaction.
    """
    order = await db.scalar(
        select(Order)
        .where(Order.id == order_id, Order.user_id == user_id)
        .options(selectinload(Order.items).joinedload(OrderItem.movie))
    )
    if order is None:
        raise OrderNotFoundError()
    if order.status != OrderStatusEnum.PENDING:
        raise OrderNotPendingError()

    purchased_ids = await get_purchased_movie_ids(
        db=db, user_id=user_id, movie_ids=[item.movie_id for item in order.items]
    )
    items_to_pay = [i for i in order.items if i.movie_id not in purchased_ids]
    if not items_to_pay:
        order.status = OrderStatusEnum.CANCELED
        await db.commit()
        raise OrderMoviesPurchasedError()
    if purchased_ids:
        await db.execute(
            delete(OrderItem).where(
                OrderItem.order_id == order.id,
                OrderItem.movie_id.in_(purchased_ids),
            )
        )
        order.total_amount = sum(
            (item.price_at_order for item in items_to_pay), Decimal(0)
        )
        await db.commit()

    return await run_in_threadpool(create_checkout_session, order.id, items_to_pay)


async def process_webhook_event(db: AsyncSession, event: Event) -> None:
    """Handle a verified Stripe event: completed or expired checkout session.

    Other events and sessions without our order_id in metadata are ignored.
    A completed session is processed only when payment_status is "paid".
    Stripe objects are turned into plain values here.
    """
    if event.type not in (CHECKOUT_COMPLETED, CHECKOUT_EXPIRED):
        return
    session = event.data.object
    if "order_id" not in session.metadata:
        return

    order_id = int(session.metadata["order_id"])
    session_id: str = session.id
    amount = Decimal(session.amount_total) / 100

    if event.type == CHECKOUT_COMPLETED:
        if session.payment_status == "paid":
            await _complete_order_payment(db, order_id, session_id, amount)
    else:
        await _cancel_order_payment(db, order_id, session_id, amount)
