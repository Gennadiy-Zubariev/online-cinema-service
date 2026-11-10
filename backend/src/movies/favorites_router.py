from typing import Annotated

from fastapi import APIRouter, status, Query

from src.accounts.dependencies import CurrentUser
from src.common.pagination import Pagination
from src.database.session import DbSession
from src.movies.favorites_service import (
    add_favorite_movie,
    remove_favorite_movie,
    list_favorite_movies,
)
from src.movies.movies_router import to_movie_list_item
from src.movies.schemas import MovieListResponse, MovieCatalogQuery

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


@router.get(
    "/favorites",
    response_model=MovieListResponse,
    status_code=status.HTTP_200_OK,
)
async def get_favorite_movie_list(
    db: DbSession,
    current_user: CurrentUser,
    pagination: Pagination,
    params: Annotated[MovieCatalogQuery, Query()],
) -> MovieListResponse:
    """List the current user's favorite movies.

    Supports the same filters, search and sorting as the movie catalog
    (`GET /movies`); `total` counts favorite movies matching them.
    Paginated: `page` starts at 1, `page_size` is 1-100 (default 20).
    """
    movies, total = await list_favorite_movies(
        db=db,
        user_id=current_user.id,
        params=params,
        page=pagination.page,
        page_size=pagination.page_size,
    )
    return MovieListResponse(
        items=[to_movie_list_item(movie) for movie in movies],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )
