from fastapi import Request, status
from fastapi.responses import JSONResponse

from src.accounts.service import MAX_AVATAR_SIZE


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


async def invalid_credentials_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={"detail": "Invalid email or password."},
        headers={"WWW-Authenticate": "Bearer"},
    )


async def user_not_active_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content={"detail": "Account is not activated. Please check your email."},
    )


async def invalid_refresh_token_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={"detail": "Invalid or expired refresh token. Please log in again."},
        headers={"WWW-Authenticate": "Bearer"},
    )


async def invalid_access_token_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={"detail": "Invalid or expired access token."},
        headers={"WWW-Authenticate": "Bearer"},
    )


async def incorrect_password_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": "Old password is incorrect."},
    )


async def invalid_password_reset_token_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "detail": "Invalid or expired password reset token. "
            "Please request a new one."
        },
    )


async def permission_denied_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content={"detail": "You do not have permission to perform this action."},
    )


async def user_not_found_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"detail": "User not found."},
    )


async def unsupported_avatar_type_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
        content={"detail": "Avatar must be a JPEG, PNG or WebP image."},
    )


async def avatar_too_large_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
        content={
            "detail": f"Avatar must not exceed {MAX_AVATAR_SIZE // (1024 * 1024)} MB."
        },
    )
