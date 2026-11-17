from datetime import UTC, datetime, timedelta

from sqlalchemy import delete
from sqlalchemy.orm import Session

from src.config.settings import Settings, get_settings
from src.database.sync_session import SyncSessionLocal
from src.orders.models import Order, OrderStatusEnum
from src.tasks.celery_app import celery_app


def delete_expired_pending_orders(session: Session, settings: Settings) -> None:
    """Delete pending orders older than PENDING_ORDER_EXPIRE_DAYS.

    Abandoned orders would otherwise block deleting their movies (RESTRICT).
    Order items and canceled payments go with them (ON DELETE CASCADE);
    paid and canceled orders are never touched.
    """
    cutoff = datetime.now(UTC) - timedelta(days=settings.PENDING_ORDER_EXPIRE_DAYS)
    session.execute(
        delete(Order).where(
            Order.status == OrderStatusEnum.PENDING, Order.created_at < cutoff
        )
    )
    session.commit()


@celery_app.task
def delete_expired_pending_orders_task() -> None:
    """Celery beat task (daily): run delete_expired_pending_orders."""
    with SyncSessionLocal() as session:
        delete_expired_pending_orders(session=session, settings=get_settings())
