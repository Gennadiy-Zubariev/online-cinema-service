from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.config.settings import get_settings

settings = get_settings()

sync_engine = create_engine(
    settings.database_url, echo=settings.DEBUG, pool_pre_ping=True
)

SyncSessionLocal = sessionmaker(bind=sync_engine, expire_on_commit=False)
