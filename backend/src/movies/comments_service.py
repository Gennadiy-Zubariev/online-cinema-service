from sqlalchemy import select, func, delete
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.movies.exceptions import EntityNotFoundError, NestedReplyError
from src.movies.models import Movie, MovieComment, CommentLike
from src.movies.schemas import CommentCreateRequest


async def create_comment(
    db: AsyncSession, user_id: int, movie_id: int, data: CommentCreateRequest
) -> MovieComment:
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
    return comment


async def list_comments(
    db: AsyncSession, movie_id: int, page: int, page_size: int
) -> tuple[list[MovieComment], int]:
    if await db.get(Movie, movie_id) is None:
        raise EntityNotFoundError(Movie.__name__)
    stmt = select(MovieComment).where(
        MovieComment.movie_id == movie_id, MovieComment.parent_id.is_(None)
    )
    total = await db.scalar(select(func.count()).select_from(stmt.subquery()))
    result = await db.scalars(
        stmt.options(selectinload(MovieComment.replies))
        .order_by(MovieComment.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(result.all()), total or 0


async def set_comment_like(db: AsyncSession, user_id: int, comment_id: int) -> None:
    if await db.get(MovieComment, comment_id) is None:
        raise EntityNotFoundError("Comment")

    stmt = insert(CommentLike).values(user_id=user_id, comment_id=comment_id)
    stmt = stmt.on_conflict_do_nothing(index_elements=["user_id", "comment_id"])
    await db.execute(stmt)
    await db.commit()


async def delete_comment_like(db: AsyncSession, user_id: int, comment_id: int) -> None:
    await db.execute(
        delete(CommentLike).where(
            CommentLike.user_id == user_id, CommentLike.comment_id == comment_id
        )
    )
    await db.commit()


async def count_comment_likes(
    db: AsyncSession, comment_ids: list[int]
) -> dict[int, int]:
    if not comment_ids:
        return {}
    result = await db.execute(
        select(CommentLike.comment_id, func.count())
        .where(CommentLike.comment_id.in_(comment_ids))
        .group_by(CommentLike.comment_id)
    )
    return {comment_id: count for comment_id, count in result.all()}
