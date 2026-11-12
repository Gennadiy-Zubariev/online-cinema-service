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
from src.movies.models import CommentLike, Movie, MovieComment
from tests.integration.conftest import (
    UNKNOWN_ID,
    Catalog,
    CreateUser,
    auth_header,
    create_caller,
)
from tests.integration.movies.conftest import movie_url

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


@pytest.fixture
async def other_movie(db_session: AsyncSession, catalog: Catalog) -> Movie:
    result = Movie(
        name="Interstellar",
        year=2014,
        time=169,
        imdb=8.7,
        votes=2000000,
        description="Explorers travel through a wormhole.",
        price=Decimal("6.99"),
        certification=catalog.certification,
    )
    db_session.add(result)
    await db_session.commit()
    return result


async def save_comment(
    db_session: AsyncSession,
    user: User,
    movie: Movie,
    text: str,
    parent: MovieComment | None = None,
) -> MovieComment:
    """Save a comment (or a reply to `parent`) directly in the DB."""
    result = MovieComment(
        user_id=user.id,
        movie_id=movie.id,
        parent_id=parent.id if parent else None,
        text=text,
    )
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
    assert body["likes"] == 0

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
    other_movie: Movie,
    comment: MovieComment,
) -> None:
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


# --- list (public) ---


def texts(items: list[dict[str, Any]]) -> list[str]:
    return [item["text"] for item in items]


async def test_list_comments_of_movie_without_comments(
    client: AsyncClient, movie: Movie
) -> None:
    response = await client.get(comments_url(movie.id))

    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0, "page": 1, "page_size": 20}


async def test_list_comments_is_public_and_nests_replies(
    client: AsyncClient,
    db_session: AsyncSession,
    user: User,
    movie: Movie,
    comment: MovieComment,
) -> None:
    reply = await save_comment(db_session, user, movie, "Agree!", parent=comment)

    response = await client.get(comments_url(movie.id))

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    [item] = body["items"]
    assert item["id"] == comment.id
    assert item["user_id"] == user.id
    assert item["movie_id"] == movie.id
    assert item["parent_id"] is None
    assert item["text"] == "Great movie!"
    assert item["created_at"] is not None
    [nested] = item["replies"]
    assert nested["id"] == reply.id
    assert nested["parent_id"] == comment.id
    assert nested["text"] == "Agree!"
    assert "replies" not in nested


async def test_list_comments_orders_roots_newest_first_and_replies_oldest_first(
    client: AsyncClient, db_session: AsyncSession, user: User, movie: Movie
) -> None:
    first = await save_comment(db_session, user, movie, "First")
    await save_comment(db_session, user, movie, "Second")
    await save_comment(db_session, user, movie, "Reply 1", parent=first)
    await save_comment(db_session, user, movie, "Reply 2", parent=first)

    response = await client.get(comments_url(movie.id))

    items = response.json()["items"]
    assert texts(items) == ["Second", "First"]
    assert texts(items[1]["replies"]) == ["Reply 1", "Reply 2"]
    assert items[0]["replies"] == []


async def test_list_comments_total_counts_only_root_comments(
    client: AsyncClient,
    db_session: AsyncSession,
    user: User,
    movie: Movie,
    comment: MovieComment,
) -> None:
    for text in ["Agree!", "Me too!"]:
        await save_comment(db_session, user, movie, text, parent=comment)

    response = await client.get(comments_url(movie.id))

    body = response.json()
    assert body["total"] == 1
    assert len(body["items"]) == 1


async def test_list_comments_excludes_other_movies(
    client: AsyncClient,
    db_session: AsyncSession,
    user: User,
    movie: Movie,
    other_movie: Movie,
    comment: MovieComment,
) -> None:
    await save_comment(db_session, user, other_movie, "Other movie comment")

    response = await client.get(comments_url(movie.id))

    body = response.json()
    assert texts(body["items"]) == ["Great movie!"]
    assert body["total"] == 1


@pytest.mark.parametrize(
    ("page", "expected"),
    [(1, ["Comment 2", "Comment 1"]), (2, ["Comment 0"]), (3, [])],
    ids=["first", "last", "past_end"],
)
async def test_list_comments_pagination(
    client: AsyncClient,
    db_session: AsyncSession,
    user: User,
    movie: Movie,
    page: int,
    expected: list[str],
) -> None:
    for i in range(3):
        await save_comment(db_session, user, movie, f"Comment {i}")

    response = await client.get(
        comments_url(movie.id), params={"page": page, "page_size": 2}
    )

    body = response.json()
    assert texts(body["items"]) == expected
    assert body["total"] == 3
    assert body["page"] == page
    assert body["page_size"] == 2


async def test_list_comments_counts_likes_of_comments_and_replies(
    client: AsyncClient,
    db_session: AsyncSession,
    create_user: CreateUser,
    user: User,
    movie: Movie,
    comment: MovieComment,
) -> None:
    other_user = await create_user(
        email="other@example.com", is_active=True, token_expires_in=None
    )
    liked_reply = await save_comment(db_session, user, movie, "Agree!", comment)
    await save_comment(db_session, user, movie, "Me too!", comment)
    db_session.add_all(
        [
            CommentLike(user_id=user.id, comment_id=comment.id),
            CommentLike(user_id=other_user.id, comment_id=comment.id),
            CommentLike(user_id=other_user.id, comment_id=liked_reply.id),
        ]
    )
    await db_session.commit()

    response = await client.get(comments_url(movie.id))

    [item] = response.json()["items"]
    assert item["likes"] == 2
    assert [reply["likes"] for reply in item["replies"]] == [1, 0]


async def test_list_comments_ignores_likes_of_other_comments(
    client: AsyncClient,
    db_session: AsyncSession,
    user: User,
    movie: Movie,
    other_movie: Movie,
    comment: MovieComment,
) -> None:
    other_comment = await save_comment(db_session, user, other_movie, "Other")
    db_session.add(CommentLike(user_id=user.id, comment_id=other_comment.id))
    await db_session.commit()

    response = await client.get(comments_url(movie.id))

    [item] = response.json()["items"]
    assert item["likes"] == 0


async def test_list_comments_loads_replies_in_fresh_session(
    client: AsyncClient,
    db_session: AsyncSession,
    user: User,
    movie: Movie,
    comment: MovieComment,
) -> None:
    """Nothing is in the identity map: replies must be eager-loaded, not lazy."""
    await save_comment(db_session, user, movie, "Agree!", parent=comment)
    db_session.expunge_all()

    response = await client.get(comments_url(movie.id))

    assert response.status_code == 200
    assert len(response.json()["items"][0]["replies"]) == 1


async def test_list_comments_of_unknown_movie_returns_404(
    client: AsyncClient, create_schema: None
) -> None:
    response = await client.get(comments_url(UNKNOWN_ID))

    assert response.status_code == 404
    assert response.json() == {"detail": "Movie not found."}


@pytest.mark.parametrize(
    "params",
    [{"page": 0}, {"page_size": 0}, {"page_size": 101}],
    ids=["page_zero", "page_size_zero", "page_size_too_big"],
)
async def test_list_comments_invalid_pagination_returns_422(
    client: AsyncClient, movie: Movie, params: dict[str, int]
) -> None:
    response = await client.get(comments_url(movie.id), params=params)

    assert response.status_code == 422
