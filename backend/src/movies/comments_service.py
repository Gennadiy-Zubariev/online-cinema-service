from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.movies.exceptions import EntityNotFoundError, NestedReplyError
from src.movies.models import Movie, MovieComment
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
