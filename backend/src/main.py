from fastapi import FastAPI

from src.accounts.exception_handlers import user_already_exists_handler
from src.accounts.exceptions import UserAlreadyExistsError
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


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


# routers
app.include_router(accounts_router, prefix=API_PREFIX)
