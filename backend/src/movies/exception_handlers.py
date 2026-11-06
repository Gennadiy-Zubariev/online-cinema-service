from fastapi import status
from fastapi.requests import Request
from fastapi.responses import JSONResponse


async def entity_not_found_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"detail": f"{exc}."},
    )


async def entity_already_exists_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": f"{exc}."},
    )


async def entity_in_use_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": f"{exc}."},
    )
