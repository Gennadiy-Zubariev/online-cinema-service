from fastapi import APIRouter, status

from src.accounts.dependencies import CurrentUser
from src.database.session import DbSession
from src.movies.comments_service import create_comment
from src.movies.models import MovieComment
from src.movies.schemas import CommentCreateRequest, CommentResponse

router = APIRouter(tags=["movies"])


@router.post(
    "/movies/{movie_id}/comments",
    response_model=CommentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_comment(
    db: DbSession, current_user: CurrentUser, movie_id: int, data: CommentCreateRequest
) -> MovieComment:
    """Comment on a movie, or reply to a comment of it (`parent_id`).

    Only one level of replies: replying to a reply returns 400.
    Returns 404 if the movie does not exist, or if `parent_id` does not
    exist or belongs to another movie.
    """
    return await create_comment(
        db=db, user_id=current_user.id, movie_id=movie_id, data=data
    )
