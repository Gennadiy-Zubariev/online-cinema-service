from fastapi import status
from fastapi.requests import Request
from fastapi.responses import JSONResponse


async def movie_already_purchase_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": f"{exc}."},
    )
