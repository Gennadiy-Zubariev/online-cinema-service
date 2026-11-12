"""Likes of comments and replies (any logged-in user)."""

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.accounts.models import User, UserGroupEnum
from src.movies.models import CommentLike, Movie, MovieComment
from tests.integration.conftest import (
    UNKNOWN_ID,
    CreateUser,
    auth_header,
    create_caller,
)


def like_url(comment_id: int) -> str:
    return f"/api/v1/comments/{comment_id}/like"


async def stored_likes(db_session: AsyncSession) -> set[tuple[int, int]]:
    """{(user_id, comment_id)} of all comment likes, read from the DB."""
    result = await db_session.execute(
        select(CommentLike.user_id, CommentLike.comment_id)
    )
    return {(user_id, comment_id) for user_id, comment_id in result.all()}


@pytest.fixture
async def user(create_user: CreateUser) -> User:
    return await create_caller(create_user, group=UserGroupEnum.USER)


@pytest.fixture
async def other_user(create_user: CreateUser) -> User:
    return await create_user(
        email="other@example.com", is_active=True, token_expires_in=None
    )


@pytest.fixture
async def comment(db_session: AsyncSession, user: User, movie: Movie) -> MovieComment:
    result = MovieComment(user_id=user.id, movie_id=movie.id, text="Great movie!")
    db_session.add(result)
    await db_session.commit()
    return result


# --- access control ---


@pytest.mark.parametrize("method", ["PUT", "DELETE"])
async def test_comment_like_requires_token(
    client: AsyncClient, comment: MovieComment, method: str
) -> None:
    response = await client.request(method, like_url(comment.id))

    assert response.status_code == 401


# --- put ---


async def test_put_comment_like(
    client: AsyncClient, db_session: AsyncSession, user: User, comment: MovieComment
) -> None:
    response = await client.put(like_url(comment.id), headers=auth_header(user))

    assert response.status_code == 204
    assert await stored_likes(db_session) == {(user.id, comment.id)}


async def test_put_comment_like_twice_keeps_one_like(
    client: AsyncClient, db_session: AsyncSession, user: User, comment: MovieComment
) -> None:
    for _ in range(2):
        response = await client.put(like_url(comment.id), headers=auth_header(user))
        assert response.status_code == 204

    assert await stored_likes(db_session) == {(user.id, comment.id)}


async def test_put_like_on_reply(
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

    response = await client.put(like_url(reply.id), headers=auth_header(user))

    assert response.status_code == 204
    assert await stored_likes(db_session) == {(user.id, reply.id)}


async def test_comment_can_be_liked_by_many_users(
    client: AsyncClient,
    db_session: AsyncSession,
    user: User,
    other_user: User,
    comment: MovieComment,
) -> None:
    for caller in [user, other_user]:
        await client.put(like_url(comment.id), headers=auth_header(caller))

    assert await stored_likes(db_session) == {
        (user.id, comment.id),
        (other_user.id, comment.id),
    }


async def test_put_like_on_unknown_comment_returns_404(
    client: AsyncClient, db_session: AsyncSession, user: User, create_schema: None
) -> None:
    response = await client.put(like_url(UNKNOWN_ID), headers=auth_header(user))

    assert response.status_code == 404
    assert response.json() == {"detail": "Comment not found."}
    assert await stored_likes(db_session) == set()


@pytest.mark.parametrize("method", ["PUT", "DELETE"])
async def test_comment_like_with_non_integer_id_returns_422(
    client: AsyncClient, user: User, method: str
) -> None:
    response = await client.request(
        method, "/api/v1/comments/abc/like", headers=auth_header(user)
    )

    assert response.status_code == 422


# --- delete ---


async def test_delete_comment_like_removes_only_own_like(
    client: AsyncClient,
    db_session: AsyncSession,
    user: User,
    other_user: User,
    comment: MovieComment,
) -> None:
    db_session.add_all(
        [
            CommentLike(user_id=user.id, comment_id=comment.id),
            CommentLike(user_id=other_user.id, comment_id=comment.id),
        ]
    )
    await db_session.commit()

    response = await client.delete(like_url(comment.id), headers=auth_header(user))

    assert response.status_code == 204
    assert await stored_likes(db_session) == {(other_user.id, comment.id)}


async def test_delete_comment_like_without_like_returns_204(
    client: AsyncClient, user: User, comment: MovieComment
) -> None:
    response = await client.delete(like_url(comment.id), headers=auth_header(user))

    assert response.status_code == 204


async def test_delete_like_of_unknown_comment_returns_204(
    client: AsyncClient, user: User
) -> None:
    response = await client.delete(like_url(UNKNOWN_ID), headers=auth_header(user))

    assert response.status_code == 204
