"""Real image bytes for upload tests (validate_image inspects the content)."""

from io import BytesIO

from PIL import Image


def make_image(image_format: str = "PNG", size: int | None = None) -> bytes:
    """Return a tiny valid image in `image_format` (Pillow name: PNG, JPEG, ...).

    `size` pads the file with trailing zero bytes up to exactly that length:
    Pillow ignores data after the end of the image, so it stays valid.
    """
    buffer = BytesIO()
    Image.new("RGB", (2, 2), "red").save(buffer, format=image_format)
    data = buffer.getvalue()
    if size is not None:
        data += b"\0" * (size - len(data))
    return data
