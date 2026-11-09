"""Likes and dislikes of movies (any logged-in user)."""

from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.accounts.models import User, UserGroupEnum
from src.movies.models import Movie, MovieReaction
from tests.integration.conftest import CreateUser
from tests.integration.movies.conftest import (
    UNKNOWN_ID,
    auth_header,
    create_caller,
    movie_url,
)


def reaction_url(movie_id: int) -> str:
    return f"{movie_url(movie_id)}/reaction"


async def stored_reactions(db_session: AsyncSession, movie_id: int) -> dict[int, bool]:
    """{user_id: is_like} for the movie, read from the DB."""
    result = await db_session.execute(
        select(MovieReaction.user_id, MovieReaction.is_like).where(
            MovieReaction.movie_id == movie_id
        )
    )
    return {user_id: is_like for user_id, is_like in result.all()}


@pytest.fixture
async def user(create_user: CreateUser) -> User:
    return await create_caller(create_user, group=UserGroupEnum.USER)


# --- access control ---


@pytest.mark.parametrize(
    ("method", "body"),
    [("PUT", {"is_like": True}), ("DELETE", None)],
    ids=["put", "delete"],
)
async def test_reaction_requires_token(
    client: AsyncClient, movie: Movie, method: str, body: dict[str, Any] | None
) -> None:
    response = await client.request(method, reaction_url(movie.id), json=body)

    assert response.status_code == 401


# --- put ---


@pytest.mark.parametrize("is_like", [True, False], ids=["like", "dislike"])
async def test_put_reaction(
    client: AsyncClient,
    db_session: AsyncSession,
    movie: Movie,
    user: User,
    is_like: bool,
) -> None:
    response = await client.put(
        reaction_url(movie.id), json={"is_like": is_like}, headers=auth_header(user)
    )

    assert response.status_code == 204
    assert response.content == b""
    assert await stored_reactions(db_session, movie.id) == {user.id: is_like}


async def test_put_reaction_replaces_previous_one(
    client: AsyncClient, db_session: AsyncSession, movie: Movie, user: User
) -> None:
    headers = auth_header(user)
    await client.put(reaction_url(movie.id), json={"is_like": True}, headers=headers)

    response = await client.put(
        reaction_url(movie.id), json={"is_like": False}, headers=headers
    )

    assert response.status_code == 204
    assert await stored_reactions(db_session, movie.id) == {user.id: False}


async def test_put_same_reaction_twice_keeps_one_row(
    client: AsyncClient, db_session: AsyncSession, movie: Movie, user: User
) -> None:
    headers = auth_header(user)
    for _ in range(2):
        response = await client.put(
            reaction_url(movie.id), json={"is_like": True}, headers=headers
        )
        assert response.status_code == 204

    assert await stored_reactions(db_session, movie.id) == {user.id: True}


async def test_reactions_of_different_users_are_independent(
    client: AsyncClient,
    create_user: CreateUser,
    db_session: AsyncSession,
    movie: Movie,
    user: User,
) -> None:
    other = await create_user(
        email="other@example.com", is_active=True, token_expires_in=None
    )

    await client.put(
        reaction_url(movie.id), json={"is_like": True}, headers=auth_header(user)
    )
    await client.put(
        reaction_url(movie.id), json={"is_like": False}, headers=auth_header(other)
    )

    assert await stored_reactions(db_session, movie.id) == {
        user.id: True,
        other.id: False,
    }


async def test_put_reaction_unknown_movie_returns_404(
    client: AsyncClient, create_schema: None, user: User
) -> None:
    response = await client.put(
        reaction_url(UNKNOWN_ID), json={"is_like": True}, headers=auth_header(user)
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Movie not found."}


@pytest.mark.parametrize(
    "body",
    [None, {}, {"is_like": None}, {"is_like": "maybe"}],
    ids=["no_body", "empty", "null", "not_bool"],
)
async def test_put_reaction_invalid_body_returns_422(
    client: AsyncClient, movie: Movie, user: User, body: dict[str, Any] | None
) -> None:
    response = await client.put(
        reaction_url(movie.id), json=body, headers=auth_header(user)
    )

    assert response.status_code == 422


# --- delete ---


async def test_delete_reaction(
    client: AsyncClient, db_session: AsyncSession, movie: Movie, user: User
) -> None:
    headers = auth_header(user)
    await client.put(reaction_url(movie.id), json={"is_like": True}, headers=headers)

    response = await client.delete(reaction_url(movie.id), headers=headers)

    assert response.status_code == 204
    assert await stored_reactions(db_session, movie.id) == {}


async def test_delete_reaction_keeps_other_users_reactions(
    client: AsyncClient,
    create_user: CreateUser,
    db_session: AsyncSession,
    movie: Movie,
    user: User,
) -> None:
    other = await create_user(
        email="other@example.com", is_active=True, token_expires_in=None
    )
    await client.put(
        reaction_url(movie.id), json={"is_like": True}, headers=auth_header(user)
    )
    await client.put(
        reaction_url(movie.id), json={"is_like": True}, headers=auth_header(other)
    )

    await client.delete(reaction_url(movie.id), headers=auth_header(user))

    assert await stored_reactions(db_session, movie.id) == {other.id: True}


@pytest.mark.parametrize(
    "unknown_movie", [False, True], ids=["no_reaction", "no_movie"]
)
async def test_delete_reaction_is_idempotent(
    client: AsyncClient, movie: Movie, user: User, unknown_movie: bool
) -> None:
    movie_id = UNKNOWN_ID if unknown_movie else movie.id

    response = await client.delete(reaction_url(movie_id), headers=auth_header(user))

    assert response.status_code == 204


async def test_deleting_movie_removes_its_reactions(
    client: AsyncClient,
    create_user: CreateUser,
    db_session: AsyncSession,
    movie: Movie,
    user: User,
) -> None:
    await client.put(
        reaction_url(movie.id), json={"is_like": True}, headers=auth_header(user)
    )
    moderator = await create_user(
        email="moderator@example.com",
        is_active=True,
        token_expires_in=None,
        group=UserGroupEnum.MODERATOR,
    )

    response = await client.delete(movie_url(movie.id), headers=auth_header(moderator))

    assert response.status_code == 204
    assert await stored_reactions(db_session, movie.id) == {}
