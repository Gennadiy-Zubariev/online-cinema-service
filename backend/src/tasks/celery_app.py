from celery import Celery

from src.config.settings import get_settings

settings = get_settings()

celery_app = Celery("online_cinema", broker=settings.redis_url)

celery_app.conf.broker_connection_retry_on_startup = True
