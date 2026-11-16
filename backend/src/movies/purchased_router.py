from typing import Annotated

from fastapi import APIRouter, status, Query

from src.accounts.dependencies import CurrentUser
from src.common.pagination import Pagination
from src.database.session import DbSession
from src.movies.movies_router import to_movie_list_item
from src.movies.purchased_service import list_purchased_movies
from src.movies.schemas import MovieListResponse, MovieCatalogQuery

router = APIRouter(tags=["movies"])


@router.get(
    "/purchased",
    response_model=MovieListResponse,
    status_code=status.HTTP_200_OK,
)
async def get_purchased_movie_list(
    db: DbSession,
    current_user: CurrentUser,
    pagination: Pagination,
    params: Annotated[MovieCatalogQuery, Query()],
) -> MovieListResponse:
    """List movies purchased by the current user ("My movies").

    Movies appear here after a successful payment.
    Supports the same filters, search and sorting as the movie catalog
    (`GET /movies`); `total` counts purchased movies matching them.
    Paginated: `page` starts at 1, `page_size` is 1-100 (default 20).
    """
    movies, total = await list_purchased_movies(
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
