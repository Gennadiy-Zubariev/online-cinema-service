from datetime import UTC, datetime, timedelta

from fastapi.concurrency import run_in_threadpool
from psycopg.errors import UniqueViolation
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.accounts.exceptions import UserAlreadyExistsError
from src.accounts.models import ActivationToken, User, UserGroup, UserGroupEnum
from src.accounts.schemas import UserRegisterRequest
from src.accounts.security import generate_token, hash_password, hash_token
from src.config.settings import Settings


async def register_user(
    db: AsyncSession, data: UserRegisterRequest, settings: Settings
) -> User:
    existing_user = await db.scalar(select(User).where(User.email == data.email))
    if existing_user is not None:
        raise UserAlreadyExistsError(data.email)

    result = await db.execute(
        select(UserGroup).where(UserGroup.name == UserGroupEnum.USER)
    )
    group = result.scalar_one()

    hashed_password = await run_in_threadpool(hash_password, data.password)
    user = User(email=data.email, hashed_password=hashed_password, group=group)

    raw_token = generate_token()
    user.activation_token = ActivationToken(
        token_hash=hash_token(raw_token),
        expires_at=datetime.now(UTC)
        + timedelta(hours=settings.ACTIVATION_TOKEN_EXPIRE_HOURS),
    )

    db.add(user)
    try:
        await db.commit()
    except IntegrityError as error:
        await db.rollback()
        if isinstance(error.orig, UniqueViolation):
            raise UserAlreadyExistsError(data.email) from error
        raise  # not an email conflict — propagate as 500

    # TODO(step 7): send_activation_email.delay(user.email, raw_token)
    return user
