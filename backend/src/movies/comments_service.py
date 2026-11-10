from sqlalchemy.ext.asyncio import AsyncSession

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
