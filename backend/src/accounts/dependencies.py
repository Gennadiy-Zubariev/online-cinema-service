from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.accounts.exceptions import InvalidAccessTokenError
from src.accounts.models import User
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
    user = await db.get(User, user_id)
    if user is None:
        raise InvalidAccessTokenError()
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
