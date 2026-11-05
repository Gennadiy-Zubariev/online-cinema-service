from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from src.accounts.exceptions import InvalidAccessTokenError, PermissionDeniedError
from src.accounts.models import User, UserGroupEnum
from src.accounts.security import decode_access_token
from src.config.settings import SettingsDep
from src.database.session import DbSession

bearer_scheme = HTTPBearer()


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
    db: DbSession,
    settings: SettingsDep,
) -> User:
    user_id = decode_access_token(credentials.credentials, settings)
    user = await db.scalar(
        select(User).where(User.id == user_id).options(joinedload(User.group))
    )
    if user is None:
        raise InvalidAccessTokenError()
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_current_admin(user: CurrentUser) -> User:
    if user.group.name != UserGroupEnum.ADMIN:
        raise PermissionDeniedError()
    return user
