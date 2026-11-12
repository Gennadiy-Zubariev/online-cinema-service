from typing import Annotated

from fastapi import APIRouter, Depends, status, UploadFile, Query

from src.accounts.dependencies import get_current_moderator
from src.common.pagination import Pagination
from src.database.session import DbSession
from src.movies.models import Movie
from src.movies.movies_service import (
    create_movie,
    update_movie,
    delete_movie,
    update_movie_poster,
    MAX_POSTER_SIZE,
    get_movie,
    list_movies,
)
from src.movies.reactions_service import get_movie_stats
from src.movies.schemas import (
    NamedEntityResponse,
    MovieCreateRequest,
    MovieResponse,
    MovieUpdateRequest,
    MovieListResponse,
    MovieListItemResponse,
    MovieCatalogQuery,
    MovieDetailResponse,
)
from src.storage.client import get_file_url

router = APIRouter(tags=["movies"])


def _to_movie_response(movie: Movie) -> MovieResponse:
    return MovieResponse(
        id=movie.id,
        uuid=movie.uuid,
        name=movie.name,
        year=movie.year,
        time=movie.time,
        imdb=movie.imdb,
        votes=movie.votes,
        meta_score=movie.meta_score,
        gross=movie.gross,
        description=movie.description,
        price=movie.price,
        certification=NamedEntityResponse(
            id=movie.certification.id, name=movie.certification.name
        ),
        genres=[
            NamedEntityResponse(id=genre.id, name=genre.name) for genre in movie.genres
        ],
        directors=[
            NamedEntityResponse(id=director.id, name=director.name)
            for director in movie.directors
        ],
        stars=[NamedEntityResponse(id=star.id, name=star.name) for star in movie.stars],
        poster_url=get_file_url(movie.poster) if movie.poster else None,
    )


@router.post(
    "/movies",
    response_model=MovieResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(get_current_moderator)],
)
async def add_movie(db: DbSession, data: MovieCreateRequest) -> MovieResponse:
    """Create a movie (moderator only).

    Catalog entities are referenced by id: `certification_id` is required,
    `genre_ids`, `director_ids` and `star_ids` are optional (duplicates are ignored).
    Returns 404 if any referenced entity does not exist.
    Returns 409 if a movie with the same name, year and duration already exists.
    """
    movie = await create_movie(db=db, data=data)
    return _to_movie_response(movie=movie)


@router.get(
    "/movies/{movie_id}",
    response_model=MovieDetailResponse,
    status_code=status.HTTP_200_OK,
)
async def get_movie_detail(db: DbSession, movie_id: int) -> MovieDetailResponse:
    """Get a movie with its certification, genres, directors and stars (public).

    `poster_url` is a temporary link (valid for 1 hour) or null.
    `rating` is the average score (1 decimal) or null if nobody rated it.
    Returns 404 if the movie does not exist.
    """
    movie = await get_movie(db=db, movie_id=movie_id)
    stats = await get_movie_stats(db=db, movie_id=movie_id)
    return MovieDetailResponse(
        **_to_movie_response(movie).model_dump(),
        likes=stats.likes,
        dislikes=stats.dislikes,
        rating=stats.rating,
        ratings_count=stats.ratings_count,
    )


def to_movie_list_item(movie: Movie) -> MovieListItemResponse:
    return MovieListItemResponse(
        id=movie.id,
        uuid=movie.uuid,
        name=movie.name,
        year=movie.year,
        time=movie.time,
        imdb=movie.imdb,
        votes=movie.votes,
        price=movie.price,
        genres=[
            NamedEntityResponse(id=genre.id, name=genre.name) for genre in movie.genres
        ],
        poster_url=get_file_url(movie.poster) if movie.poster else None,
    )


@router.get(
    "/movies",
    response_model=MovieListResponse,
    status_code=status.HTTP_200_OK,
)
async def get_movie_list(
    db: DbSession, pagination: Pagination, params: Annotated[MovieCatalogQuery, Query()]
) -> MovieListResponse:
    """List movies of the catalog (public).

    Filters (optional, bounds inclusive): `year_from` / `year_to`,
    `imdb_min` / `imdb_max`. An inverted range returns an empty list.
    `genre_id` returns movies of that genre (unknown id - an empty list).
    Sorting: `sort_by` is `id` (default), `price`, `year` (release date)
    or `votes` (popularity); `order` is `asc` (default) or `desc`.
    Movies with equal sort values are ordered by id, so pages are stable.
    Paginated: `page` starts at 1, `page_size` is 1-100 (default 20);
    `total` counts all movies matching the filters.
    Search: search matches name, description,
    star or director (case-insensitive substring).
    A page past the end returns an empty `items` list.
    """
    movies, total = await list_movies(
        db=db, params=params, page=pagination.page, page_size=pagination.page_size
    )
    return MovieListResponse(
        items=[to_movie_list_item(movie) for movie in movies],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.patch(
    "/movies/{movie_id}",
    response_model=MovieResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(get_current_moderator)],
)
async def edit_movie(
    db: DbSession, movie_id: int, data: MovieUpdateRequest
) -> MovieResponse:
    """Partially update a movie (moderator only).

    Only the fields sent are changed; `meta_score` and `gross` can be cleared
    with null, other fields cannot be null. A list of ids (`genre_ids`, ...)
    replaces the current set; send [] to remove all.
    Returns 404 if the movie or any referenced entity does not exist.
    Returns 409 if another movie has the same name, year and duration.
    """
    movie = await update_movie(db=db, movie_id=movie_id, data=data)
    return _to_movie_response(movie=movie)


@router.put(
    "/movies/{movie_id}/poster",
    response_model=MovieResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(get_current_moderator)],
)
async def upload_movie_poster(
    db: DbSession, movie_id: int, file: UploadFile
) -> MovieResponse:
    """Upload or replace a movie poster (moderator only).

    Accepts JPEG, PNG or WebP up to 5 MB (415 / 413 otherwise).
    The previous poster file is deleted.
    Returns 404 if the movie does not exist.
    """
    data = await file.read(MAX_POSTER_SIZE + 1)
    movie = await update_movie_poster(
        db=db, movie_id=movie_id, data=data, content_type=file.content_type
    )
    return _to_movie_response(movie)


@router.delete(
    "/movies/{movie_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(get_current_moderator)],
)
async def remove_movie(db: DbSession, movie_id: int) -> None:
    """Delete a movie and its poster (moderator only).

    Its links to genres, directors and stars are removed as well;
    the catalog entities themselves are kept. The movie is removed from carts.
    Returns 404 if the movie does not exist.
    Returns 409 if the movie is in at least one order.
    """
    await delete_movie(db=db, movie_id=movie_id)
