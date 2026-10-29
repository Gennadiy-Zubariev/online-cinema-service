from fastapi import Request, status
from fastapi.responses import JSONResponse


async def user_already_exists_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": "User with this email already exists."},
    )
