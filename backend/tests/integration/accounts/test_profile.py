from unittest.mock import MagicMock

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.accounts.models import User, UserProfile
from src.accounts.security import create_access_token
from src.accounts.service import MAX_AVATAR_SIZE
from src.config.settings import get_settings
from tests.integration.conftest import CreateUser

PROFILE_URL = "/api/v1/accounts/profile"
AVATAR_URL = "/api/v1/accounts/profile/avatar"
EMPTY_PROFILE = {
    "first_name": None,
    "last_name": None,
    "gender": None,
    "date_of_birth": None,
    "info": None,
    "avatar_url": None,
}


def auth_header(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user.id, get_settings())}"}


@pytest.fixture
def storage_mock(monkeypatch: pytest.MonkeyPatch) -> dict[str, MagicMock]:
    """Replace S3 calls where the service uses them, so tests need no MinIO."""
    mocks = {"upload_file": MagicMock(), "delete_file": MagicMock()}
    for name, mock in mocks.items():
        monkeypatch.setattr(f"src.accounts.service.{name}", mock)
    return mocks


async def stored_profile(db_session: AsyncSession, user: User) -> UserProfile | None:
    return await db_session.scalar(
        select(UserProfile).where(UserProfile.user_id == user.id)
    )


# --- GET / PATCH ---


async def test_get_profile_without_profile_returns_empty(
    client: AsyncClient, db_session: AsyncSession, create_user: CreateUser
) -> None:
    user = await create_user(is_active=True)

    response = await client.get(PROFILE_URL, headers=auth_header(user))

    assert response.status_code == 200
    assert response.json() == EMPTY_PROFILE
    assert await stored_profile(db_session, user) is None  # GET writes nothing


async def test_patch_creates_profile(
    client: AsyncClient, db_session: AsyncSession, create_user: CreateUser
) -> None:
    user = await create_user(is_active=True)
    payload = {
        "first_name": "Gena",
        "last_name": "Z",
        "gender": "man",
        "date_of_birth": "1990-05-17",
        "info": "Movie fan",
    }

    response = await client.patch(PROFILE_URL, json=payload, headers=auth_header(user))

    assert response.status_code == 200
    assert response.json() == {**payload, "avatar_url": None}
    assert await stored_profile(db_session, user) is not None
    get_response = await client.get(PROFILE_URL, headers=auth_header(user))
    assert get_response.json() == response.json()


async def test_patch_changes_only_sent_fields(
    client: AsyncClient, create_user: CreateUser
) -> None:
    user = await create_user(is_active=True)
    headers = auth_header(user)
    await client.patch(
        PROFILE_URL, json={"first_name": "Gena", "info": "Fan"}, headers=headers
    )

    response = await client.patch(
        PROFILE_URL, json={"last_name": "Z", "info": None}, headers=headers
    )

    body = response.json()
    assert body["first_name"] == "Gena"  # not sent -> unchanged
    assert body["last_name"] == "Z"
    assert body["info"] is None  # explicit null -> cleared


async def test_patch_edits_only_own_profile(
    client: AsyncClient, db_session: AsyncSession, create_user: CreateUser
) -> None:
    user = await create_user(email="user@example.com", is_active=True)
    other = await create_user(
        email="other@example.com", is_active=True, token_expires_in=None
    )

    await client.patch(
        PROFILE_URL, json={"first_name": "Gena"}, headers=auth_header(user)
    )

    assert await stored_profile(db_session, other) is None


@pytest.mark.parametrize(
    "payload",
    [
        {"first_name": "x" * 101},
        {"info": "x" * 1001},
        {"date_of_birth": "2999-01-01"},
        {"gender": "unknown"},
    ],
    ids=["long_first_name", "long_info", "future_date_of_birth", "unknown_gender"],
)
async def test_patch_rejects_invalid_payload(
    client: AsyncClient, create_user: CreateUser, payload: dict[str, str]
) -> None:
    user = await create_user(is_active=True)

    response = await client.patch(PROFILE_URL, json=payload, headers=auth_header(user))

    assert response.status_code == 422


@pytest.mark.parametrize(
    ("method", "url"),
    [("GET", PROFILE_URL), ("PATCH", PROFILE_URL), ("PUT", AVATAR_URL)],
    ids=["get", "patch", "avatar"],
)
async def test_profile_endpoints_require_token(
    client: AsyncClient, method: str, url: str
) -> None:
    response = await client.request(method, url)

    assert response.status_code == 401


# --- avatar ---


async def test_upload_avatar_stores_key_and_returns_url(
    client: AsyncClient,
    db_session: AsyncSession,
    create_user: CreateUser,
    storage_mock: dict[str, MagicMock],
) -> None:
    user = await create_user(is_active=True)

    response = await client.put(
        AVATAR_URL,
        files={"file": ("my photo.PNG", b"png-bytes", "image/png")},
        headers=auth_header(user),
    )

    assert response.status_code == 200
    storage_mock["upload_file"].assert_called_once()
    key, data, content_type = storage_mock["upload_file"].call_args.args
    # The key is generated by the server, the original file name is ignored.
    assert key.startswith(f"avatars/{user.id}/")
    assert key.endswith(".png")
    assert "photo" not in key
    assert (data, content_type) == (b"png-bytes", "image/png")

    profile = await stored_profile(db_session, user)
    assert profile is not None
    assert profile.avatar == key
    avatar_url = response.json()["avatar_url"]
    assert avatar_url.startswith(get_settings().S3_PUBLIC_ENDPOINT_URL)
    assert key in avatar_url
    storage_mock["delete_file"].assert_not_called()


async def test_upload_avatar_replaces_and_deletes_old_file(
    client: AsyncClient,
    create_user: CreateUser,
    storage_mock: dict[str, MagicMock],
) -> None:
    user = await create_user(is_active=True)
    headers = auth_header(user)
    await client.put(
        AVATAR_URL, files={"file": ("a.png", b"old", "image/png")}, headers=headers
    )
    old_key = storage_mock["upload_file"].call_args.args[0]

    await client.put(
        AVATAR_URL, files={"file": ("b.jpg", b"new", "image/jpeg")}, headers=headers
    )

    new_key = storage_mock["upload_file"].call_args.args[0]
    assert new_key != old_key
    assert new_key.endswith(".jpg")
    storage_mock["delete_file"].assert_called_once_with(old_key)


async def test_patch_profile_keeps_avatar(
    client: AsyncClient,
    create_user: CreateUser,
    storage_mock: dict[str, MagicMock],
) -> None:
    user = await create_user(is_active=True)
    headers = auth_header(user)
    await client.put(
        AVATAR_URL, files={"file": ("a.png", b"img", "image/png")}, headers=headers
    )

    response = await client.patch(
        PROFILE_URL, json={"first_name": "Gena"}, headers=headers
    )

    assert response.json()["avatar_url"] is not None


@pytest.mark.parametrize("content_type", ["image/gif", "image/svg+xml", "text/plain"])
async def test_upload_avatar_rejects_unsupported_type(
    client: AsyncClient,
    create_user: CreateUser,
    storage_mock: dict[str, MagicMock],
    content_type: str,
) -> None:
    user = await create_user(is_active=True)

    response = await client.put(
        AVATAR_URL,
        files={"file": ("file", b"data", content_type)},
        headers=auth_header(user),
    )

    assert response.status_code == 415
    assert response.json() == {"detail": "Image must be a JPEG, PNG or WebP image."}
    storage_mock["upload_file"].assert_not_called()


async def test_upload_avatar_rejects_too_large_file(
    client: AsyncClient,
    create_user: CreateUser,
    storage_mock: dict[str, MagicMock],
) -> None:
    user = await create_user(is_active=True)

    response = await client.put(
        AVATAR_URL,
        files={"file": ("big.png", b"x" * (MAX_AVATAR_SIZE + 1), "image/png")},
        headers=auth_header(user),
    )

    assert response.status_code == 413
    assert response.json() == {"detail": "Image must not exceed 2 MB."}
    storage_mock["upload_file"].assert_not_called()


async def test_upload_avatar_accepts_file_of_max_size(
    client: AsyncClient,
    create_user: CreateUser,
    storage_mock: dict[str, MagicMock],
) -> None:
    user = await create_user(is_active=True)

    response = await client.put(
        AVATAR_URL,
        files={"file": ("max.png", b"x" * MAX_AVATAR_SIZE, "image/png")},
        headers=auth_header(user),
    )

    assert response.status_code == 200


async def test_upload_avatar_requires_file(
    client: AsyncClient, create_user: CreateUser
) -> None:
    user = await create_user(is_active=True)

    response = await client.put(AVATAR_URL, headers=auth_header(user))

    assert response.status_code == 422
