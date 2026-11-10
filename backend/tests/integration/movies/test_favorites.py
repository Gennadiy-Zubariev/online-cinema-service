"""Favorite movies of the current user (any logged-in user)."""

from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.accounts.models import User, UserGroupEnum
from src.movies.models import FavoriteMovie, Movie
from tests.integration.conftest import CreateUser
from tests.integration.movies.conftest import (
    UNKNOWN_ID,
    auth_header,
    create_caller,
    movie_url,
)


def favorite_url(movie_id: int) -> str:
    return f"{movie_url(movie_id)}/favorite"


async def stored_favorites(db_session: AsyncSession) -> set[tuple[int, int]]:
    """{(user_id, movie_id)} of all favorites, read from the DB."""
    result = await db_session.execute(
        select(FavoriteMovie.user_id, FavoriteMovie.movie_id)
    )
    return {(user_id, movie_id) for user_id, movie_id in result.all()}


@pytest.fixture
async def user(create_user: CreateUser) -> User:
    return await create_caller(create_user, group=UserGroupEnum.USER)


@pytest.fixture
async def other_user(create_user: CreateUser) -> User:
    return await create_user(
        email="other@example.com", is_active=True, token_expires_in=None
    )


# --- access control ---


@pytest.mark.parametrize("method", ["PUT", "DELETE"])
async def test_favorite_requires_token(
    client: AsyncClient, movie: Movie, method: str
) -> None:
    response = await client.request(method, favorite_url(movie.id))

    assert response.status_code == 401


# --- put ---


async def test_put_favorite(
    client: AsyncClient, db_session: AsyncSession, user: User, movie: Movie
) -> None:
    response = await client.put(favorite_url(movie.id), headers=auth_header(user))

    assert response.status_code == 204
    assert await stored_favorites(db_session) == {(user.id, movie.id)}


async def test_put_favorite_sets_added_at(
    client: AsyncClient, db_session: AsyncSession, user: User, movie: Movie
) -> None:
    await client.put(favorite_url(movie.id), headers=auth_header(user))

    added_at = await db_session.scalar(select(FavoriteMovie.added_at))
    assert added_at is not None


async def test_put_favorite_twice_keeps_one_row_and_added_at(
    client: AsyncClient, db_session: AsyncSession, user: User, movie: Movie
) -> None:
    """`added_at` is set explicitly: inside the test transaction `now()` never
    changes, so a second PUT that overwrote it would go unnoticed otherwise."""
    added_at = datetime(2020, 1, 1, tzinfo=UTC)
    db_session.add(FavoriteMovie(user_id=user.id, movie_id=movie.id, added_at=added_at))
    await db_session.commit()

    response = await client.put(favorite_url(movie.id), headers=auth_header(user))

    assert response.status_code == 204
    assert await stored_favorites(db_session) == {(user.id, movie.id)}
    assert await db_session.scalar(select(FavoriteMovie.added_at)) == added_at


async def test_movie_can_be_favorite_of_many_users(
    client: AsyncClient,
    db_session: AsyncSession,
    user: User,
    other_user: User,
    movie: Movie,
) -> None:
    for caller in [user, other_user]:
        await client.put(favorite_url(movie.id), headers=auth_header(caller))

    assert await stored_favorites(db_session) == {
        (user.id, movie.id),
        (other_user.id, movie.id),
    }


async def test_put_favorite_of_unknown_movie_returns_404(
    client: AsyncClient, db_session: AsyncSession, user: User
) -> None:
    response = await client.put(favorite_url(UNKNOWN_ID), headers=auth_header(user))

    assert response.status_code == 404
    assert response.json() == {"detail": "Movie not found."}
    assert await stored_favorites(db_session) == set()


@pytest.mark.parametrize("method", ["PUT", "DELETE"])
async def test_favorite_with_non_integer_id_returns_422(
    client: AsyncClient, user: User, method: str
) -> None:
    response = await client.request(
        method, "/api/v1/movies/abc/favorite", headers=auth_header(user)
    )

    assert response.status_code == 422


# --- delete ---


async def test_delete_favorite_removes_only_own(
    client: AsyncClient,
    db_session: AsyncSession,
    user: User,
    other_user: User,
    movie: Movie,
) -> None:
    db_session.add_all(
        [
            FavoriteMovie(user_id=user.id, movie_id=movie.id),
            FavoriteMovie(user_id=other_user.id, movie_id=movie.id),
        ]
    )
    await db_session.commit()

    response = await client.delete(favorite_url(movie.id), headers=auth_header(user))

    assert response.status_code == 204
    assert await stored_favorites(db_session) == {(other_user.id, movie.id)}


async def test_delete_favorite_not_in_favorites_returns_204(
    client: AsyncClient, user: User, movie: Movie
) -> None:
    response = await client.delete(favorite_url(movie.id), headers=auth_header(user))

    assert response.status_code == 204


async def test_delete_favorite_of_unknown_movie_returns_204(
    client: AsyncClient, user: User
) -> None:
    response = await client.delete(favorite_url(UNKNOWN_ID), headers=auth_header(user))

    assert response.status_code == 204
