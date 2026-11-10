from fastapi import APIRouter, status

from src.accounts.dependencies import CurrentUser
from src.database.session import DbSession
from src.movies.reactions_service import (
    set_movie_reaction,
    delete_movie_reaction,
    set_movie_rating,
    delete_movie_rating,
)
from src.movies.schemas import MovieReactionRequest, MovieRatingRequest

router = APIRouter(tags=["movies"])


@router.put(
    "/movies/{movie_id}/reaction",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def put_movie_reaction(
    db: DbSession, current_user: CurrentUser, movie_id: int, data: MovieReactionRequest
) -> None:
    """Like (`is_like: true`) or dislike (`false`) a movie.

    A user has at most one reaction per movie: a new one replaces the old.
    Returns 404 if the movie does not exist.
    """
    await set_movie_reaction(
        db=db, user_id=current_user.id, movie_id=movie_id, is_like=data.is_like
    )


@router.delete(
    "/movies/{movie_id}/reaction",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_movie_reaction(
    db: DbSession, current_user: CurrentUser, movie_id: int
) -> None:
    """Remove the current user's like or dislike from a movie.

    Idempotent: returns 204 even if there was no reaction.
    """
    await delete_movie_reaction(db=db, user_id=current_user.id, movie_id=movie_id)


@router.put(
    "/movies/{movie_id}/rating",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def put_movie_rating(
    db: DbSession, current_user: CurrentUser, movie_id: int, data: MovieRatingRequest
) -> None:
    """Rate a movie from 1 to 10.

    A user has at most one rating per movie: a new one replaces the old.
    Returns 404 if the movie does not exist.
    """
    await set_movie_rating(
        db=db, user_id=current_user.id, movie_id=movie_id, score=data.score
    )


@router.delete(
    "/movies/{movie_id}/rating",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_movie_rating(
    db: DbSession, current_user: CurrentUser, movie_id: int
) -> None:
    """Remove the current user's rating of a movie.

    Idempotent: returns 204 even if there was no rating.
    """
    await delete_movie_rating(db=db, user_id=current_user.id, movie_id=movie_id)
