from fastapi import Request, status
from fastapi.responses import JSONResponse


async def unsupported_image_type_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
        content={"detail": "Image must be a JPEG, PNG or WebP image."},
    )


async def image_too_large_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
        content={"detail": f"{exc}."},
    )
