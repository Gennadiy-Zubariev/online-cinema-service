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
    """Return the active user from the Bearer access token, with the group loaded.

    Raises InvalidAccessTokenError (401) if the token is invalid, the user
    no longer exists or is deactivated: the check runs on every request,
    so deactivation takes effect without waiting for the token to expire.
    """
    user_id = decode_access_token(credentials.credentials, settings)
    user = await db.scalar(
        select(User).where(User.id == user_id).options(joinedload(User.group))
    )
    if user is None or not user.is_active:
        raise InvalidAccessTokenError()
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_current_admin(user: CurrentUser) -> User:
    """Allow only admins; otherwise raise PermissionDeniedError (403)."""
    if user.group.name != UserGroupEnum.ADMIN:
        raise PermissionDeniedError()
    return user


AdminUser = Annotated[User, Depends(get_current_admin)]


async def get_current_moderator(user: CurrentUser) -> User:
    """Allow moderators and admins; otherwise raise PermissionDeniedError (403)."""
    if user.group.name not in (UserGroupEnum.MODERATOR, UserGroupEnum.ADMIN):
        raise PermissionDeniedError()
    return user
