from fastapi import status
from fastapi.requests import Request
from fastapi.responses import JSONResponse


async def invalid_webhook_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": f"{exc}"},
    )
