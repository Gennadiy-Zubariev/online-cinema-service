from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.concurrency import run_in_threadpool

from src.accounts.exception_handlers import (
    user_already_exists_handler,
    invalid_activation_token_handler,
    expired_activation_token_handler,
    invalid_credentials_handler,
    user_not_active_handler,
    invalid_refresh_token_handler,
    invalid_access_token_handler,
    incorrect_password_handler,
    invalid_password_reset_token_handler,
    permission_denied_handler,
    user_not_found_handler,
)
from src.accounts.exceptions import (
    UserAlreadyExistsError,
    InvalidActivationTokenError,
    ActivationTokenExpiredError,
    InvalidCredentialsError,
    UserNotActiveError,
    InvalidRefreshTokenError,
    InvalidAccessTokenError,
    IncorrectPasswordError,
    InvalidPasswordResetTokenError,
    PermissionDeniedError,
    UserNotFoundError,
)
from src.accounts.router import router as accounts_router
from src.config.settings import get_settings
from src.movies.comments_router import router as movie_comments_router
from src.movies.entities_router import router as movie_entities_router
from src.movies.exception_handlers import (
    entity_not_found_handler,
    entity_already_exists_handler,
    entity_in_use_handler,
    nested_reply_handler,
)
from src.movies.exceptions import (
    EntityNotFoundError,
    EntityAlreadyExistsError,
    EntityInUseError,
    NestedReplyError,
)
from src.movies.movies_router import router as movies_router
from src.movies.reactions_router import router as movie_reactions_router
from src.storage.client import ensure_bucket_exists
from src.storage.exception_handlers import (
    unsupported_image_type_handler,
    image_too_large_handler,
)
from src.storage.exceptions import UnsupportedImageTypeError, ImageTooLargeError

settings = get_settings()

API_PREFIX = "/api/v1"


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    await run_in_threadpool(ensure_bucket_exists)
    yield


app = FastAPI(title=settings.PROJECT_NAME, debug=settings.DEBUG, lifespan=lifespan)

# exception handlers
app.add_exception_handler(UserAlreadyExistsError, user_already_exists_handler)
app.add_exception_handler(InvalidActivationTokenError, invalid_activation_token_handler)
app.add_exception_handler(ActivationTokenExpiredError, expired_activation_token_handler)
app.add_exception_handler(InvalidCredentialsError, invalid_credentials_handler)
app.add_exception_handler(UserNotActiveError, user_not_active_handler)
app.add_exception_handler(InvalidRefreshTokenError, invalid_refresh_token_handler)
app.add_exception_handler(InvalidAccessTokenError, invalid_access_token_handler)
app.add_exception_handler(IncorrectPasswordError, incorrect_password_handler)
app.add_exception_handler(
    InvalidPasswordResetTokenError, invalid_password_reset_token_handler
)
app.add_exception_handler(PermissionDeniedError, permission_denied_handler)
app.add_exception_handler(UserNotFoundError, user_not_found_handler)
app.add_exception_handler(UnsupportedImageTypeError, unsupported_image_type_handler)
app.add_exception_handler(ImageTooLargeError, image_too_large_handler)
app.add_exception_handler(EntityNotFoundError, entity_not_found_handler)
app.add_exception_handler(EntityAlreadyExistsError, entity_already_exists_handler)
app.add_exception_handler(EntityInUseError, entity_in_use_handler)
app.add_exception_handler(NestedReplyError, nested_reply_handler)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


# routers
app.include_router(accounts_router, prefix=API_PREFIX)
app.include_router(movie_entities_router, prefix=API_PREFIX)
app.include_router(movies_router, prefix=API_PREFIX)
app.include_router(movie_reactions_router, prefix=API_PREFIX)
app.include_router(movie_comments_router, prefix=API_PREFIX)
