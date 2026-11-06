import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.accounts.models import ActivationToken, User, UserGroup, UserGroupEnum
from src.accounts.security import create_access_token
from src.config.settings import get_settings
from tests.integration.conftest import CreateUser

USERS_URL = "/api/v1/accounts/users"
PERMISSION_DENIED = {"detail": "You do not have permission to perform this action."}
USER_NOT_FOUND = {"detail": "User not found."}


def auth_header(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user.id, get_settings())}"}


async def create_admin(create_user: CreateUser) -> User:
    return await create_user(
        email="admin@example.com",
        is_active=True,
        token_expires_in=None,
        group=UserGroupEnum.ADMIN,
    )


async def group_name_of(db_session: AsyncSession, user_id: int) -> str | None:
    return await db_session.scalar(
        select(UserGroup.name).join(User.group).where(User.id == user_id)
    )


# --- access control (same dependency on every admin endpoint) ---

ADMIN_ENDPOINTS = [
    ("GET", USERS_URL, None),
    ("PATCH", f"{USERS_URL}/{{user_id}}/group", {"group": "moderator"}),
    ("POST", f"{USERS_URL}/{{user_id}}/activate", None),
]
ENDPOINT_IDS = ["list", "change_group", "activate"]


@pytest.mark.parametrize(("method", "url", "body"), ADMIN_ENDPOINTS, ids=ENDPOINT_IDS)
@pytest.mark.parametrize("group", [UserGroupEnum.USER, UserGroupEnum.MODERATOR])
async def test_admin_endpoints_reject_non_admin(
    client: AsyncClient,
    create_user: CreateUser,
    method: str,
    url: str,
    body: dict[str, str] | None,
    group: UserGroupEnum,
) -> None:
    caller = await create_user(is_active=True, token_expires_in=None, group=group)

    response = await client.request(
        method, url.format(user_id=caller.id), json=body, headers=auth_header(caller)
    )

    assert response.status_code == 403
    assert response.json() == PERMISSION_DENIED


@pytest.mark.parametrize(("method", "url", "body"), ADMIN_ENDPOINTS, ids=ENDPOINT_IDS)
async def test_admin_endpoints_require_token(
    client: AsyncClient, method: str, url: str, body: dict[str, str] | None
) -> None:
    response = await client.request(method, url.format(user_id=1), json=body)

    assert response.status_code == 401


async def test_non_admin_gets_403_before_404(
    client: AsyncClient, create_user: CreateUser
) -> None:
    # Permission is checked first: a non-admin learns nothing about other users.
    caller = await create_user(is_active=True, token_expires_in=None)

    response = await client.post(
        f"{USERS_URL}/999999/activate", headers=auth_header(caller)
    )

    assert response.status_code == 403


# --- change group ---


async def test_change_group_updates_user_group(
    client: AsyncClient, db_session: AsyncSession, create_user: CreateUser
) -> None:
    admin = await create_admin(create_user)
    user = await create_user(is_active=True)

    response = await client.patch(
        f"{USERS_URL}/{user.id}/group",
        json={"group": "moderator"},
        headers=auth_header(admin),
    )

    assert response.status_code == 200
    assert response.json() == {"message": "User group updated."}
    assert await group_name_of(db_session, user.id) == UserGroupEnum.MODERATOR


async def test_change_group_unknown_user_returns_404(
    client: AsyncClient, create_user: CreateUser
) -> None:
    admin = await create_admin(create_user)

    response = await client.patch(
        f"{USERS_URL}/999999/group",
        json={"group": "moderator"},
        headers=auth_header(admin),
    )

    assert response.status_code == 404
    assert response.json() == USER_NOT_FOUND


async def test_change_group_rejects_unknown_group(
    client: AsyncClient, db_session: AsyncSession, create_user: CreateUser
) -> None:
    admin = await create_admin(create_user)
    user = await create_user(is_active=True)

    response = await client.patch(
        f"{USERS_URL}/{user.id}/group",
        json={"group": "superuser"},
        headers=auth_header(admin),
    )

    assert response.status_code == 422
    assert await group_name_of(db_session, user.id) == UserGroupEnum.USER


# --- manual activation ---


async def test_activate_activates_user_and_deletes_token(
    client: AsyncClient, db_session: AsyncSession, create_user: CreateUser
) -> None:
    admin = await create_admin(create_user)
    user = await create_user(is_active=False)

    response = await client.post(
        f"{USERS_URL}/{user.id}/activate", headers=auth_header(admin)
    )

    assert response.status_code == 200
    assert response.json() == {"message": "User activated."}
    await db_session.refresh(user)
    assert user.is_active is True
    token = await db_session.scalar(
        select(ActivationToken).where(ActivationToken.user_id == user.id)
    )
    assert token is None


async def test_activate_already_active_user_returns_200(
    client: AsyncClient, create_user: CreateUser
) -> None:
    admin = await create_admin(create_user)
    user = await create_user(is_active=True, token_expires_in=None)

    response = await client.post(
        f"{USERS_URL}/{user.id}/activate", headers=auth_header(admin)
    )

    assert response.status_code == 200


async def test_admin_can_activate_self(
    client: AsyncClient, create_user: CreateUser
) -> None:
    # The admin is already in the session without `activation_token` loaded:
    # `db.get` would return it as is -> lazy load -> MissingGreenlet (500).
    admin = await create_admin(create_user)

    response = await client.post(
        f"{USERS_URL}/{admin.id}/activate", headers=auth_header(admin)
    )

    assert response.status_code == 200


async def test_activate_unknown_user_returns_404(
    client: AsyncClient, create_user: CreateUser
) -> None:
    admin = await create_admin(create_user)

    response = await client.post(
        f"{USERS_URL}/999999/activate", headers=auth_header(admin)
    )

    assert response.status_code == 404
    assert response.json() == USER_NOT_FOUND


# --- list users ---


async def test_list_users_returns_users_with_group(
    client: AsyncClient, create_user: CreateUser
) -> None:
    admin = await create_admin(create_user)
    user = await create_user(email="user@example.com", is_active=False)

    response = await client.get(USERS_URL, headers=auth_header(admin))

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert body["page"] == 1
    assert body["page_size"] == 20
    assert [item["id"] for item in body["items"]] == [admin.id, user.id]
    item = body["items"][1]
    assert item["email"] == "user@example.com"
    assert item["is_active"] is False
    assert item["group"] == {"name": "user"}
    assert "created_at" in item
    assert "hashed_password" not in item


async def test_list_users_paginates_by_id(
    client: AsyncClient, create_user: CreateUser
) -> None:
    admin = await create_admin(create_user)
    # One shared RAW_ACTIVATION_TOKEN per factory -> create these without tokens.
    users = [
        await create_user(email=f"user{i}@example.com", token_expires_in=None)
        for i in range(3)
    ]

    response = await client.get(
        USERS_URL, params={"page": 2, "page_size": 2}, headers=auth_header(admin)
    )

    body = response.json()
    assert body["total"] == 4
    assert [item["id"] for item in body["items"]] == [users[1].id, users[2].id]


async def test_list_users_page_beyond_end_is_empty(
    client: AsyncClient, create_user: CreateUser
) -> None:
    admin = await create_admin(create_user)

    response = await client.get(
        USERS_URL, params={"page": 5}, headers=auth_header(admin)
    )

    assert response.status_code == 200
    assert response.json()["items"] == []
    assert response.json()["total"] == 1


@pytest.mark.parametrize(
    "params",
    [{"page": 0}, {"page_size": 0}, {"page_size": 101}],
    ids=["page_zero", "page_size_zero", "page_size_too_big"],
)
async def test_list_users_rejects_invalid_pagination(
    client: AsyncClient, create_user: CreateUser, params: dict[str, int]
) -> None:
    admin = await create_admin(create_user)

    response = await client.get(USERS_URL, params=params, headers=auth_header(admin))

    assert response.status_code == 422
