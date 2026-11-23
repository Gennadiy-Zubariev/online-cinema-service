from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.accounts.models import (
    ActivationToken,
    RefreshToken,
    User,
    UserGroup,
    UserGroupEnum,
)
from src.accounts.security import create_access_token, generate_token, hash_token
from src.config.settings import get_settings
from tests.integration.conftest import USER_PASSWORD, CreateUser

USERS_URL = "/api/v1/accounts/users"
PERMISSION_DENIED = {"detail": "You do not have permission to perform this action."}
USER_NOT_FOUND = {"detail": "User not found."}
LOGIN_URL = "/api/v1/accounts/login"
REFRESH_URL = "/api/v1/accounts/refresh"
PROFILE_URL = "/api/v1/accounts/profile"


def auth_header(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user.id, get_settings())}"}


async def create_admin(create_user: CreateUser) -> User:
    return await create_user(
        email="admin@example.com",
        is_active=True,
        token_expires_in=None,
        group=UserGroupEnum.ADMIN,
    )


async def save_refresh_tokens(
    db_session: AsyncSession, user: User, count: int = 2
) -> None:
    """Sessions on `count` devices, saved directly in DB."""
    for _ in range(count):
        db_session.add(
            RefreshToken(
                user_id=user.id,
                token_hash=hash_token(generate_token()),
                expires_at=datetime.now(UTC) + timedelta(days=7),
            )
        )
    await db_session.commit()


async def refresh_token_count(db_session: AsyncSession, user: User) -> int | None:
    return await db_session.scalar(
        select(func.count())
        .select_from(RefreshToken)
        .where(RefreshToken.user_id == user.id)
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
    ("POST", f"{USERS_URL}/{{user_id}}/deactivate", None),
]
ENDPOINT_IDS = ["list", "change_group", "activate", "deactivate"]


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


async def test_activate_inactive_user_deletes_old_refresh_tokens(
    client: AsyncClient, db_session: AsyncSession, create_user: CreateUser
) -> None:
    # Sessions issued before the user became inactive must not come back.
    admin = await create_admin(create_user)
    user = await create_user(is_active=False, token_expires_in=None)
    await save_refresh_tokens(db_session, user)

    response = await client.post(
        f"{USERS_URL}/{user.id}/activate", headers=auth_header(admin)
    )

    assert response.status_code == 200
    assert await refresh_token_count(db_session, user) == 0


async def test_activate_active_user_keeps_refresh_tokens(
    client: AsyncClient, db_session: AsyncSession, create_user: CreateUser
) -> None:
    # Idempotent call must not log an active user out.
    admin = await create_admin(create_user)
    user = await create_user(is_active=True, token_expires_in=None)
    await save_refresh_tokens(db_session, user)

    response = await client.post(
        f"{USERS_URL}/{user.id}/activate", headers=auth_header(admin)
    )

    assert response.status_code == 200
    assert await refresh_token_count(db_session, user) == 2


async def test_activate_lifts_deactivation(
    client: AsyncClient, db_session: AsyncSession, create_user: CreateUser
) -> None:
    admin = await create_admin(create_user)
    user = await create_user(is_active=False, token_expires_in=None)
    user.deactivated_at = datetime.now(UTC)
    await db_session.commit()

    response = await client.post(
        f"{USERS_URL}/{user.id}/activate", headers=auth_header(admin)
    )

    assert response.status_code == 200
    await db_session.refresh(user)
    assert user.is_active is True
    assert user.deactivated_at is None


# --- manual deactivation ---


async def test_deactivate_deactivates_user_and_deletes_tokens(
    client: AsyncClient, db_session: AsyncSession, create_user: CreateUser
) -> None:
    admin = await create_admin(create_user)
    user = await create_user(is_active=True)  # with an activation token
    await save_refresh_tokens(db_session, user)

    response = await client.post(
        f"{USERS_URL}/{user.id}/deactivate", headers=auth_header(admin)
    )

    assert response.status_code == 200
    assert response.json() == {"message": "User deactivated."}
    await db_session.refresh(user)
    assert user.is_active is False
    assert user.deactivated_at is not None
    assert await refresh_token_count(db_session, user) == 0
    token = await db_session.scalar(
        select(ActivationToken).where(ActivationToken.user_id == user.id)
    )
    assert token is None


async def test_deactivate_keeps_other_users_tokens(
    client: AsyncClient, db_session: AsyncSession, create_user: CreateUser
) -> None:
    admin = await create_admin(create_user)
    user = await create_user(is_active=True, token_expires_in=None)
    other = await create_user(
        email="other@example.com", is_active=True, token_expires_in=None
    )
    await save_refresh_tokens(db_session, other)

    await client.post(f"{USERS_URL}/{user.id}/deactivate", headers=auth_header(admin))

    assert await refresh_token_count(db_session, other) == 2


async def test_deactivate_ends_sessions_at_once(
    client: AsyncClient, create_user: CreateUser
) -> None:
    # Both tokens of the user stop working: refresh (deleted) and access
    # (get_current_user checks is_active) - no waiting for 15 min TTL.
    admin = await create_admin(create_user)
    user = await create_user(is_active=True, token_expires_in=None)
    login = await client.post(
        LOGIN_URL, json={"email": user.email, "password": USER_PASSWORD}
    )
    access_token = login.json()["access_token"]

    await client.post(f"{USERS_URL}/{user.id}/deactivate", headers=auth_header(admin))

    assert (await client.post(REFRESH_URL)).status_code == 401
    profile = await client.get(
        PROFILE_URL, headers={"Authorization": f"Bearer {access_token}"}
    )
    assert profile.status_code == 401


async def test_deactivate_then_activate_does_not_revive_old_sessions(
    client: AsyncClient, create_user: CreateUser
) -> None:
    admin = await create_admin(create_user)
    user = await create_user(is_active=True, token_expires_in=None)
    await client.post(LOGIN_URL, json={"email": user.email, "password": USER_PASSWORD})
    old_cookie = client.cookies["refresh_token"]

    await client.post(f"{USERS_URL}/{user.id}/deactivate", headers=auth_header(admin))
    await client.post(f"{USERS_URL}/{user.id}/activate", headers=auth_header(admin))
    client.cookies.set("refresh_token", old_cookie)

    assert (await client.post(REFRESH_URL)).status_code == 401
    login = await client.post(
        LOGIN_URL, json={"email": user.email, "password": USER_PASSWORD}
    )
    assert login.status_code == 200


async def test_deactivate_already_deactivated_keeps_first_time(
    client: AsyncClient, db_session: AsyncSession, create_user: CreateUser
) -> None:
    admin = await create_admin(create_user)
    user = await create_user(is_active=False, token_expires_in=None)
    first_time = datetime(2026, 1, 1, tzinfo=UTC)
    user.deactivated_at = first_time
    await db_session.commit()

    response = await client.post(
        f"{USERS_URL}/{user.id}/deactivate", headers=auth_header(admin)
    )

    assert response.status_code == 200
    await db_session.refresh(user)
    assert user.deactivated_at == first_time


async def test_deactivate_self_returns_400(
    client: AsyncClient, db_session: AsyncSession, create_user: CreateUser
) -> None:
    # Otherwise the only admin could lock everyone out of the admin panel.
    admin = await create_admin(create_user)

    response = await client.post(
        f"{USERS_URL}/{admin.id}/deactivate", headers=auth_header(admin)
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "You cannot deactivate your own account."}
    await db_session.refresh(admin)
    assert admin.is_active is True


async def test_deactivate_unknown_user_returns_404(
    client: AsyncClient, create_user: CreateUser
) -> None:
    admin = await create_admin(create_user)

    response = await client.post(
        f"{USERS_URL}/999999/deactivate", headers=auth_header(admin)
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
    assert item["deactivated_at"] is None
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
