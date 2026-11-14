from decimal import Decimal

from fastapi.concurrency import run_in_threadpool
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.movies.purchased_service import get_purchased_movie_ids
from src.orders.exceptions import (
    OrderMoviesPurchasedError,
    OrderNotFoundError,
    OrderNotPendingError,
)
from src.orders.models import Order, OrderItem, OrderStatusEnum
from src.payments.stripe_client import create_checkout_session


async def start_checkout(db: AsyncSession, user_id: int, order_id: int) -> str:
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
