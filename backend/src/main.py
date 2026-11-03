from fastapi import FastAPI

from src.accounts.exception_handlers import (
    user_already_exists_handler,
    invalid_activation_token_handler,
    expired_activation_token_handler,
    invalid_credentials_handler,
    user_not_active_handler,
    invalid_refresh_token_handler,
)
from src.accounts.exceptions import (
    UserAlreadyExistsError,
    InvalidActivationTokenError,
    ActivationTokenExpiredError,
    InvalidCredentialsError,
    UserNotActiveError,
    InvalidRefreshTokenError,
)
from src.accounts.router import router as accounts_router
from src.config.settings import get_settings

settings = get_settings()

API_PREFIX = "/api/v1"

app = FastAPI(
    title=settings.PROJECT_NAME,
    debug=settings.DEBUG,
)

# exception handlers
app.add_exception_handler(UserAlreadyExistsError, user_already_exists_handler)
app.add_exception_handler(InvalidActivationTokenError, invalid_activation_token_handler)
app.add_exception_handler(ActivationTokenExpiredError, expired_activation_token_handler)
app.add_exception_handler(InvalidCredentialsError, invalid_credentials_handler)
app.add_exception_handler(UserNotActiveError, user_not_active_handler)
app.add_exception_handler(InvalidRefreshTokenError, invalid_refresh_token_handler)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


# routers
app.include_router(accounts_router, prefix=API_PREFIX)
