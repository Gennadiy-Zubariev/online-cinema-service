from fastapi import Request, status
from fastapi.responses import JSONResponse


async def user_already_exists_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": "User with this email already exists."},
    )


async def invalid_activation_token_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": "Invalid or already used activation token."},
    )


async def expired_activation_token_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": "Activation token has expired. Please request a new one."},
    )
