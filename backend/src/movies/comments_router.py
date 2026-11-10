from fastapi import APIRouter, status

from src.accounts.dependencies import CurrentUser
from src.common.pagination import Pagination
from src.database.session import DbSession
from src.movies.comments_service import create_comment, list_comments
from src.movies.models import MovieComment
from src.movies.schemas import (
    CommentCreateRequest,
    CommentResponse,
    CommentListResponse,
    CommentWithRepliesResponse,
)

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


@router.get(
    "/movies/{movie_id}/comments",
    response_model=CommentListResponse,
    status_code=status.HTTP_200_OK,
)
async def get_comment_list(
    db: DbSession, movie_id: int, pagination: Pagination
) -> CommentListResponse:
    """List comments of a movie with their replies (public).

    Top-level comments are paginated, newest first: `page` starts at 1,
    `page_size` is 1-100 (default 20); `total` counts top-level comments only.
    Each comment has all its `replies`, oldest first.
    Returns 404 if the movie does not exist.
    """
    comments, total = await list_comments(
        db=db, movie_id=movie_id, page=pagination.page, page_size=pagination.page_size
    )
    return CommentListResponse(
        items=[CommentWithRepliesResponse.model_validate(c) for c in comments],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )
