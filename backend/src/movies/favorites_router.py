from fastapi import APIRouter, status

from src.accounts.dependencies import CurrentUser
from src.database.session import DbSession
from src.movies.favorites_service import add_favorite_movie, remove_favorite_movie

router = APIRouter(tags=["movies"])


@router.put(
    "/movies/{movie_id}/favorite",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def put_favorite_movie(
    db: DbSession, current_user: CurrentUser, movie_id: int
) -> None:
    """Add a movie to the current user's favorites.

    Idempotent: adding an already favorite movie changes nothing.
    Returns 404 if the movie does not exist.
    """
    await add_favorite_movie(db=db, user_id=current_user.id, movie_id=movie_id)


@router.delete(
    "/movies/{movie_id}/favorite",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_favorite_movie(
    db: DbSession, current_user: CurrentUser, movie_id: int
) -> None:
    """Remove a movie from the current user's favorites.

    Idempotent: returns 204 even if the movie was not a favorite.
    """
    await remove_favorite_movie(db=db, user_id=current_user.id, movie_id=movie_id)
