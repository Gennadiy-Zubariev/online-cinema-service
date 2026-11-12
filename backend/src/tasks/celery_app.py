from celery import Celery
from celery.schedules import crontab

from src.config.settings import get_settings

settings = get_settings()

celery_app = Celery(
    "online_cinema",
    broker=settings.redis_url,
    include=["src.tasks.emails", "src.tasks.accounts", "src.tasks.orders"],
)

celery_app.conf.broker_connection_retry_on_startup = True


celery_app.conf.beat_schedule = {
    "delete-expired-tokens": {
        "task": "src.tasks.accounts.delete_expired_tokens_task",
        "schedule": crontab(minute=0),  # every hour at :00
    },
    "delete-expired-pending-orders": {
        "task": "src.tasks.orders.delete_expired_pending_orders_task",
        "schedule": crontab(minute=30, hour=3),  # every day at 03:30 UTC
    },
}
