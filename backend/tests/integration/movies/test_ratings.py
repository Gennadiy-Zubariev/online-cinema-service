"""Ratings of movies on a 1-10 scale (any logged-in user)."""

from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.accounts.models import User, UserGroupEnum
from src.movies.models import Movie, MovieRating
from tests.integration.conftest import CreateUser
from tests.integration.movies.conftest import (
    UNKNOWN_ID,
    auth_header,
    create_caller,
    movie_url,
)


def rating_url(movie_id: int) -> str:
    return f"{movie_url(movie_id)}/rating"


async def stored_ratings(db_session: AsyncSession, movie_id: int) -> dict[int, int]:
    """{user_id: score} for the movie, read from the DB."""
    result = await db_session.execute(
        select(MovieRating.user_id, MovieRating.score).where(
            MovieRating.movie_id == movie_id
        )
    )
    return {user_id: score for user_id, score in result.all()}


@pytest.fixture
async def user(create_user: CreateUser) -> User:
    return await create_caller(create_user, group=UserGroupEnum.USER)


# --- access control ---


@pytest.mark.parametrize(
    ("method", "body"),
    [("PUT", {"score": 8}), ("DELETE", None)],
    ids=["put", "delete"],
)
async def test_rating_requires_token(
    client: AsyncClient, movie: Movie, method: str, body: dict[str, Any] | None
) -> None:
    response = await client.request(method, rating_url(movie.id), json=body)

    assert response.status_code == 401


# --- put ---


@pytest.mark.parametrize("score", [1, 7, 10], ids=["min", "middle", "max"])
async def test_put_rating(
    client: AsyncClient,
    db_session: AsyncSession,
    movie: Movie,
    user: User,
    score: int,
) -> None:
    response = await client.put(
        rating_url(movie.id), json={"score": score}, headers=auth_header(user)
    )

    assert response.status_code == 204
    assert response.content == b""
    assert await stored_ratings(db_session, movie.id) == {user.id: score}


async def test_put_rating_replaces_previous_one(
    client: AsyncClient, db_session: AsyncSession, movie: Movie, user: User
) -> None:
    headers = auth_header(user)
    await client.put(rating_url(movie.id), json={"score": 3}, headers=headers)

    response = await client.put(
        rating_url(movie.id), json={"score": 9}, headers=headers
    )

    assert response.status_code == 204
    assert await stored_ratings(db_session, movie.id) == {user.id: 9}


async def test_ratings_of_different_users_are_independent(
    client: AsyncClient,
    create_user: CreateUser,
    db_session: AsyncSession,
    movie: Movie,
    user: User,
) -> None:
    other = await create_user(
        email="other@example.com", is_active=True, token_expires_in=None
    )

    await client.put(rating_url(movie.id), json={"score": 4}, headers=auth_header(user))
    await client.put(
        rating_url(movie.id), json={"score": 10}, headers=auth_header(other)
    )

    assert await stored_ratings(db_session, movie.id) == {user.id: 4, other.id: 10}


async def test_rating_and_reaction_are_independent(
    client: AsyncClient, db_session: AsyncSession, movie: Movie, user: User
) -> None:
    headers = auth_header(user)
    await client.put(
        f"{movie_url(movie.id)}/reaction", json={"is_like": False}, headers=headers
    )

    response = await client.put(
        rating_url(movie.id), json={"score": 6}, headers=headers
    )
    await client.delete(f"{movie_url(movie.id)}/reaction", headers=headers)

    assert response.status_code == 204
    assert await stored_ratings(db_session, movie.id) == {user.id: 6}


async def test_put_rating_unknown_movie_returns_404(
    client: AsyncClient, create_schema: None, user: User
) -> None:
    response = await client.put(
        rating_url(UNKNOWN_ID), json={"score": 5}, headers=auth_header(user)
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Movie not found."}


@pytest.mark.parametrize(
    "body",
    [
        None,
        {},
        {"score": None},
        {"score": 0},
        {"score": 11},
        {"score": -1},
        {"score": 7.5},
        {"score": "high"},
    ],
    ids=[
        "no_body",
        "empty",
        "null",
        "zero",
        "above_10",
        "negative",
        "fraction",
        "not_int",
    ],
)
async def test_put_rating_invalid_body_returns_422(
    client: AsyncClient,
    db_session: AsyncSession,
    movie: Movie,
    user: User,
    body: dict[str, Any] | None,
) -> None:
    response = await client.put(
        rating_url(movie.id), json=body, headers=auth_header(user)
    )

    assert response.status_code == 422
    assert await stored_ratings(db_session, movie.id) == {}


# --- delete ---


async def test_delete_rating(
    client: AsyncClient, db_session: AsyncSession, movie: Movie, user: User
) -> None:
    headers = auth_header(user)
    await client.put(rating_url(movie.id), json={"score": 8}, headers=headers)

    response = await client.delete(rating_url(movie.id), headers=headers)

    assert response.status_code == 204
    assert await stored_ratings(db_session, movie.id) == {}


async def test_delete_rating_keeps_other_users_ratings(
    client: AsyncClient,
    create_user: CreateUser,
    db_session: AsyncSession,
    movie: Movie,
    user: User,
) -> None:
    other = await create_user(
        email="other@example.com", is_active=True, token_expires_in=None
    )
    await client.put(rating_url(movie.id), json={"score": 8}, headers=auth_header(user))
    await client.put(
        rating_url(movie.id), json={"score": 2}, headers=auth_header(other)
    )

    await client.delete(rating_url(movie.id), headers=auth_header(user))

    assert await stored_ratings(db_session, movie.id) == {other.id: 2}


@pytest.mark.parametrize("unknown_movie", [False, True], ids=["no_rating", "no_movie"])
async def test_delete_rating_is_idempotent(
    client: AsyncClient, movie: Movie, user: User, unknown_movie: bool
) -> None:
    movie_id = UNKNOWN_ID if unknown_movie else movie.id

    response = await client.delete(rating_url(movie_id), headers=auth_header(user))

    assert response.status_code == 204


async def test_deleting_movie_removes_its_ratings(
    client: AsyncClient,
    create_user: CreateUser,
    db_session: AsyncSession,
    movie: Movie,
    user: User,
) -> None:
    await client.put(rating_url(movie.id), json={"score": 8}, headers=auth_header(user))
    moderator = await create_user(
        email="moderator@example.com",
        is_active=True,
        token_expires_in=None,
        group=UserGroupEnum.MODERATOR,
    )

    response = await client.delete(movie_url(movie.id), headers=auth_header(moderator))

    assert response.status_code == 204
    assert await stored_ratings(db_session, movie.id) == {}
