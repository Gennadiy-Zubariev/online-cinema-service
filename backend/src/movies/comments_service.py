from sqlalchemy import select, func, delete
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.accounts.models import User
from src.movies.exceptions import EntityNotFoundError, NestedReplyError
from src.movies.models import Movie, MovieComment, CommentLike
from src.movies.schemas import CommentCreateRequest

# Comment author with the profile: its name is shown next to the comment.
AUTHOR_LOADER = selectinload(MovieComment.author).selectinload(User.profile)


async def create_comment(
    db: AsyncSession, user_id: int, movie_id: int, data: CommentCreateRequest
) -> MovieComment:
    """Create a comment, or a reply when parent_id is set.

    Raises EntityNotFoundError for an unknown movie, or a parent that is missing
    or belongs to another movie; NestedReplyError for a reply to a reply
    (only one level of replies).
    """
    if await db.get(Movie, movie_id) is None:
        raise EntityNotFoundError(Movie.__name__)
    if data.parent_id is not None:
        parent = await db.get(MovieComment, data.parent_id)
        if parent is None or parent.movie_id != movie_id:
            raise EntityNotFoundError("Comment")
        if parent.parent_id is not None:
            raise NestedReplyError()
    comment = MovieComment(
        user_id=user_id, movie_id=movie_id, parent_id=data.parent_id, text=data.text
    )
    db.add(comment)
    await db.commit()
    # Reload with the author: the response needs the author's name.
    result = await db.execute(
        select(MovieComment)
        .where(MovieComment.id == comment.id)
        .options(AUTHOR_LOADER)
        .execution_options(populate_existing=True)
    )
    return result.scalar_one()


async def list_comments(
    db: AsyncSession, movie_id: int, page: int, page_size: int
) -> tuple[list[MovieComment], int]:
    """Return (top-level comments newest first with replies loaded, total).

    Authors (with profiles) of comments and replies are loaded too.

    Raises EntityNotFoundError for an unknown movie. total counts only
    top-level comments.
    """
    if await db.get(Movie, movie_id) is None:
        raise EntityNotFoundError(Movie.__name__)
    stmt = select(MovieComment).where(
        MovieComment.movie_id == movie_id, MovieComment.parent_id.is_(None)
    )
    total = await db.scalar(select(func.count()).select_from(stmt.subquery()))
    result = await db.scalars(
        stmt.options(
            AUTHOR_LOADER,
            selectinload(MovieComment.replies)
            .selectinload(MovieComment.author)
            .selectinload(User.profile),
        )
        .order_by(MovieComment.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(result.all()), total or 0


async def set_comment_like(db: AsyncSession, user_id: int, comment_id: int) -> None:
    """Like a comment; idempotent. Raises EntityNotFoundError."""
    if await db.get(MovieComment, comment_id) is None:
        raise EntityNotFoundError("Comment")

    stmt = insert(CommentLike).values(user_id=user_id, comment_id=comment_id)
    stmt = stmt.on_conflict_do_nothing(index_elements=["user_id", "comment_id"])
    await db.execute(stmt)
    await db.commit()


async def delete_comment_like(db: AsyncSession, user_id: int, comment_id: int) -> None:
    """Remove the user's like; idempotent, no existence checks."""
    await db.execute(
        delete(CommentLike).where(
            CommentLike.user_id == user_id, CommentLike.comment_id == comment_id
        )
    )
    await db.commit()


async def count_comment_likes(
    db: AsyncSession, comment_ids: list[int]
) -> dict[int, int]:
    """Return {comment_id: likes} in one GROUP BY query.

    Comments without likes are absent from the result: use .get(id, 0).
    """
    if not comment_ids:
        return {}
    result = await db.execute(
        select(CommentLike.comment_id, func.count())
        .where(CommentLike.comment_id.in_(comment_ids))
        .group_by(CommentLike.comment_id)
    )
    return {comment_id: count for comment_id, count in result.all()}
