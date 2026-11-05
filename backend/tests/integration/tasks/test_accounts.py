from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.accounts.models import (
    ActivationToken,
    PasswordResetToken,
    RefreshToken,
    User,
    UserGroup,
    UserGroupEnum,
)
from src.accounts.security import hash_token
from src.tasks.accounts import delete_expired_tokens

TokenModel = type[ActivationToken] | type[PasswordResetToken] | type[RefreshToken]


def create_user_with_token(
    session: Session, email: str, token_model: TokenModel, expires_in: timedelta
) -> User:
    group = session.scalar(
        select(UserGroup).where(UserGroup.name == UserGroupEnum.USER)
    )
    user = User(email=email, hashed_password="not-a-real-hash", group=group)
    session.add(user)
    session.flush()  # assigns user.id for the token FK
    session.add(
        token_model(
            token_hash=hash_token(email),
            expires_at=datetime.now(UTC) + expires_in,
            user_id=user.id,
        )
    )
    session.commit()
    return user


@pytest.mark.parametrize(
    "token_model",
    [ActivationToken, PasswordResetToken, RefreshToken],
    ids=["activation", "password_reset", "refresh"],
)
def test_delete_expired_tokens_keeps_only_valid_ones(
    sync_db_session: Session, token_model: TokenModel
) -> None:
    create_user_with_token(
        sync_db_session, "expired@example.com", token_model, timedelta(seconds=-1)
    )
    valid_user = create_user_with_token(
        sync_db_session, "valid@example.com", token_model, timedelta(hours=1)
    )

    delete_expired_tokens(sync_db_session)

    remaining_user_ids = sync_db_session.scalars(select(token_model.user_id)).all()
    assert remaining_user_ids == [valid_user.id]


def test_delete_expired_tokens_keeps_users(sync_db_session: Session) -> None:
    create_user_with_token(
        sync_db_session, "expired@example.com", ActivationToken, timedelta(seconds=-1)
    )

    delete_expired_tokens(sync_db_session)

    user = sync_db_session.scalar(
        select(User).where(User.email == "expired@example.com")
    )
    assert user is not None
