class StorageError(Exception):
    """Base class for storage errors."""


class UnsupportedImageTypeError(StorageError):
    """Raised when the uploaded file is not a JPEG, PNG or WebP image."""


class ImageTooLargeError(StorageError):
    """Raised when the uploaded image exceeds the allowed size."""

    def __init__(self, max_size: int):
        self.max_size = max_size
        super().__init__(f"Image must not exceed {max_size // (1024 * 1024)} MB")
