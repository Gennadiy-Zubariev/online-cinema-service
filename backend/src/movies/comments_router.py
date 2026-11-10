from fastapi import APIRouter, status

from src.accounts.dependencies import CurrentUser
from src.common.pagination import Pagination
from src.database.session import DbSession
from src.movies.comments_service import (
    create_comment,
    list_comments,
    set_comment_like,
    delete_comment_like,
    count_comment_likes,
)
from src.movies.models import MovieComment
from src.movies.schemas import (
    CommentCreateRequest,
    CommentResponse,
    CommentListResponse,
    CommentWithRepliesResponse,
)

router = APIRouter(tags=["movies"])


def _to_comment_response(comment: MovieComment, likes: int) -> CommentResponse:
    return CommentResponse(
        id=comment.id,
        user_id=comment.user_id,
        movie_id=comment.movie_id,
        parent_id=comment.parent_id,
        text=comment.text,
        created_at=comment.created_at,
        likes=likes,
    )


def _to_comment_with_replies(
    comment: MovieComment, likes: dict[int, int]
) -> CommentWithRepliesResponse:
    return CommentWithRepliesResponse(
        **_to_comment_response(comment, likes.get(comment.id, 0)).model_dump(),
        replies=[
            _to_comment_response(reply, likes.get(reply.id, 0))
            for reply in comment.replies
        ],
    )


@router.post(
    "/movies/{movie_id}/comments",
    response_model=CommentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_comment(
    db: DbSession, current_user: CurrentUser, movie_id: int, data: CommentCreateRequest
) -> CommentResponse:
    """Comment on a movie, or reply to a comment of it (`parent_id`).

    Only one level of replies: replying to a reply returns 400.
    Returns 404 if the movie does not exist, or if `parent_id` does not
    exist or belongs to another movie.
    """
    comment = await create_comment(
        db=db, user_id=current_user.id, movie_id=movie_id, data=data
    )
    return _to_comment_response(comment, likes=0)


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
    comment_ids = []
    for comment in comments:
        comment_ids.append(comment.id)
        comment_ids.extend(reply.id for reply in comment.replies)
    likes = await count_comment_likes(db=db, comment_ids=comment_ids)
    return CommentListResponse(
        items=[_to_comment_with_replies(comment, likes) for comment in comments],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.put(
    "/comments/{comment_id}/like",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def put_comment_like(
    db: DbSession, current_user: CurrentUser, comment_id: int
) -> None:
    """Like a comment or a reply.

    Idempotent: liking an already liked comment changes nothing.
    Returns 404 if the comment does not exist.
    """
    await set_comment_like(db=db, user_id=current_user.id, comment_id=comment_id)


@router.delete(
    "/comments/{comment_id}/like",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_comment_like(
    db: DbSession, current_user: CurrentUser, comment_id: int
) -> None:
    """Remove the current user's like from a comment.

    Idempotent: returns 204 even if there was no like.
    """
    await delete_comment_like(db=db, user_id=current_user.id, comment_id=comment_id)
