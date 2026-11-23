from io import BytesIO

from PIL import Image

from src.storage.exceptions import ImageTooLargeError, UnsupportedImageTypeError

# Pillow format name -> (content type, file extension)
IMAGE_FORMATS = {
    "JPEG": ("image/jpeg", "jpg"),
    "PNG": ("image/png", "png"),
    "WEBP": ("image/webp", "webp"),
}


def validate_image(data: bytes, max_size: int) -> tuple[str, str]:
    """Detect the real image format from the bytes; return content type and extension.

    The client's Content-Type is not trusted: Pillow reads the file header
    (only JPEG / PNG / WebP parsers are tried) and verify() checks the file
    structure without decoding pixels. Size is checked first, so oversized
    files are not parsed. Raises ImageTooLargeError or UnsupportedImageTypeError.
    """
    if len(data) > max_size:
        raise ImageTooLargeError(max_size)
    try:
        with Image.open(BytesIO(data), formats=list(IMAGE_FORMATS)) as image:
            image_format = image.format
            image.verify()
    except (OSError, SyntaxError, ValueError, Image.DecompressionBombError) as exc:
        raise UnsupportedImageTypeError() from exc
    if image_format is None or image_format not in IMAGE_FORMATS:
        raise UnsupportedImageTypeError()
    return IMAGE_FORMATS[image_format]
