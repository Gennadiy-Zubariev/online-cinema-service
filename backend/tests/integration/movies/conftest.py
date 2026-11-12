"""Shared constants and helpers for movies integration tests.

Fixtures used by several domains (`catalog`, `movie`, `auth_header`, ...)
live in `tests/integration/conftest.py`.
"""

MOVIES_URL = "/api/v1/movies"
PERMISSION_DENIED = {"detail": "You do not have permission to perform this action."}


def movie_url(movie_id: int) -> str:
    return f"{MOVIES_URL}/{movie_id}"
