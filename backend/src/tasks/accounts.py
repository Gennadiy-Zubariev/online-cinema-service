from datetime import datetime, UTC

from sqlalchemy import delete
from sqlalchemy.orm import Session

from src.accounts.models import ActivationToken, PasswordResetToken, RefreshToken
from src.database.sync_session import SyncSessionLocal
from src.tasks.celery_app import celery_app

TOKEN_MODELS = (ActivationToken, PasswordResetToken, RefreshToken)


def delete_expired_tokens(session: Session) -> None:
    now = datetime.now(UTC)
    for token_model in TOKEN_MODELS:
        session.execute(delete(token_model).where(token_model.expires_at < now))
    session.commit()


@celery_app.task
def delete_expired_tokens_task() -> None:
    with SyncSessionLocal() as session:
        delete_expired_tokens(session=session)
