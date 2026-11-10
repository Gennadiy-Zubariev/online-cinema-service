"""Comments on movies and replies to them (any logged-in user).

Only one level of replies: a reply cannot be replied to.
"""

from decimal import Decimal
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.accounts.models import User, UserGroupEnum
from src.movies.models import Movie, MovieComment
from tests.integration.conftest import CreateUser
from tests.integration.movies.conftest import (
    UNKNOWN_ID,
    Catalog,
    auth_header,
    create_caller,
    movie_url,
)

COMMENT_NOT_FOUND = {"detail": "Comment not found."}


def comments_url(movie_id: int) -> str:
    return f"{movie_url(movie_id)}/comments"


@pytest.fixture
async def user(create_user: CreateUser) -> User:
    return await create_caller(create_user, group=UserGroupEnum.USER)


@pytest.fixture
async def comment(db_session: AsyncSession, user: User, movie: Movie) -> MovieComment:
    """Saved root comment of `movie`."""
    result = MovieComment(user_id=user.id, movie_id=movie.id, text="Great movie!")
    db_session.add(result)
    await db_session.commit()
    return result


async def stored_comments(db_session: AsyncSession) -> list[MovieComment]:
    result = await db_session.scalars(select(MovieComment).order_by(MovieComment.id))
    return list(result.all())


# --- access control ---


async def test_create_comment_requires_token(client: AsyncClient, movie: Movie) -> None:
    response = await client.post(comments_url(movie.id), json={"text": "Hi"})

    assert response.status_code == 401


# --- root comment ---


async def test_create_comment(
    client: AsyncClient, db_session: AsyncSession, user: User, movie: Movie
) -> None:
    response = await client.post(
        comments_url(movie.id), json={"text": "Great movie!"}, headers=auth_header(user)
    )

    assert response.status_code == 201
    body = response.json()
    assert body["user_id"] == user.id
    assert body["movie_id"] == movie.id
    assert body["parent_id"] is None
    assert body["text"] == "Great movie!"
    assert body["created_at"] is not None

    [stored] = await stored_comments(db_session)
    assert stored.id == body["id"]
    assert stored.parent_id is None


async def test_create_comment_strips_text(
    client: AsyncClient, user: User, movie: Movie
) -> None:
    response = await client.post(
        comments_url(movie.id), json={"text": "  Great!  "}, headers=auth_header(user)
    )

    assert response.json()["text"] == "Great!"


async def test_create_comment_accepts_text_of_max_length(
    client: AsyncClient, user: User, movie: Movie
) -> None:
    response = await client.post(
        comments_url(movie.id), json={"text": "a" * 2000}, headers=auth_header(user)
    )

    assert response.status_code == 201


async def test_user_can_comment_one_movie_many_times(
    client: AsyncClient, db_session: AsyncSession, user: User, movie: Movie
) -> None:
    for text in ["First", "Second"]:
        response = await client.post(
            comments_url(movie.id), json={"text": text}, headers=auth_header(user)
        )
        assert response.status_code == 201

    assert [c.text for c in await stored_comments(db_session)] == ["First", "Second"]


async def test_create_comment_for_unknown_movie_returns_404(
    client: AsyncClient, db_session: AsyncSession, user: User, create_schema: None
) -> None:
    response = await client.post(
        comments_url(UNKNOWN_ID), json={"text": "Hi"}, headers=auth_header(user)
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Movie not found."}
    assert await stored_comments(db_session) == []


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"text": ""},
        {"text": "   "},
        {"text": "a" * 2001},
        {"text": "Hi", "parent_id": "abc"},
    ],
    ids=["missing_text", "empty", "whitespace", "too_long", "bad_parent_id"],
)
async def test_create_comment_invalid_body_returns_422(
    client: AsyncClient, user: User, movie: Movie, body: dict[str, Any]
) -> None:
    response = await client.post(
        comments_url(movie.id), json=body, headers=auth_header(user)
    )

    assert response.status_code == 422


# --- reply ---


async def test_reply_to_comment(
    client: AsyncClient,
    db_session: AsyncSession,
    create_user: CreateUser,
    movie: Movie,
    comment: MovieComment,
) -> None:
    other_user = await create_user(
        email="other@example.com", is_active=True, token_expires_in=None
    )

    response = await client.post(
        comments_url(movie.id),
        json={"text": "Agree!", "parent_id": comment.id},
        headers=auth_header(other_user),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["parent_id"] == comment.id
    assert body["movie_id"] == movie.id
    assert body["user_id"] == other_user.id

    stored = await stored_comments(db_session)
    assert [c.parent_id for c in stored] == [None, comment.id]


async def test_reply_to_unknown_comment_returns_404(
    client: AsyncClient, user: User, movie: Movie
) -> None:
    response = await client.post(
        comments_url(movie.id),
        json={"text": "Agree!", "parent_id": UNKNOWN_ID},
        headers=auth_header(user),
    )

    assert response.status_code == 404
    assert response.json() == COMMENT_NOT_FOUND


async def test_reply_to_comment_of_another_movie_returns_404(
    client: AsyncClient,
    db_session: AsyncSession,
    user: User,
    catalog: Catalog,
    comment: MovieComment,
) -> None:
    other_movie = Movie(
        name="Interstellar",
        year=2014,
        time=169,
        imdb=8.7,
        votes=2000000,
        description="Explorers travel through a wormhole.",
        price=Decimal("6.99"),
        certification=catalog.certification,
    )
    db_session.add(other_movie)
    await db_session.commit()

    response = await client.post(
        comments_url(other_movie.id),
        json={"text": "Agree!", "parent_id": comment.id},
        headers=auth_header(user),
    )

    assert response.status_code == 404
    assert response.json() == COMMENT_NOT_FOUND
    assert len(await stored_comments(db_session)) == 1


async def test_reply_to_reply_returns_400(
    client: AsyncClient,
    db_session: AsyncSession,
    user: User,
    movie: Movie,
    comment: MovieComment,
) -> None:
    reply = MovieComment(
        user_id=user.id, movie_id=movie.id, parent_id=comment.id, text="Agree!"
    )
    db_session.add(reply)
    await db_session.commit()

    response = await client.post(
        comments_url(movie.id),
        json={"text": "Me too!", "parent_id": reply.id},
        headers=auth_header(user),
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Replies to replies are not allowed."}
    assert len(await stored_comments(db_session)) == 2


async def test_reply_to_comment_of_unknown_movie_returns_movie_404(
    client: AsyncClient, user: User, comment: MovieComment
) -> None:
    """The movie is checked first: its 404 wins over any parent problem."""
    response = await client.post(
        comments_url(UNKNOWN_ID),
        json={"text": "Agree!", "parent_id": comment.id},
        headers=auth_header(user),
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Movie not found."}
