from typing import Annotated

from fastapi import APIRouter, Depends, status, UploadFile, Query

from src.accounts.dependencies import get_current_moderator, CurrentUser
from src.common.pagination import Pagination
from src.database.session import DbSession
from src.movies.models import Certification, Director, Genre, Star, Movie
from src.movies.schemas import (
    NamedEntityRequest,
    NamedEntityResponse,
    NamedEntityListResponse,
    MovieCreateRequest,
    MovieResponse,
    MovieUpdateRequest,
    MovieListResponse,
    MovieListItemResponse,
    MovieCatalogQuery,
    MovieReactionRequest,
)
from src.movies.service import (
    create_named,
    list_named,
    get_named,
    update_named,
    delete_named,
    create_movie,
    update_movie,
    delete_movie,
    update_movie_poster,
    MAX_POSTER_SIZE,
    get_movie,
    list_movies,
    set_movie_reaction,
    delete_movie_reaction,
)
from src.storage.client import get_file_url

router = APIRouter(tags=["movies"])


@router.post(
    "/genres",
    response_model=NamedEntityResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(get_current_moderator)],
)
async def create_genre(db: DbSession, data: NamedEntityRequest) -> Genre:
    """Create a genre (moderator only).

    Leading and trailing whitespace in the name is stripped.
    Returns 409 if a genre with this name already exists.
    """
    return await create_named(db=db, model=Genre, name=data.name)


@router.get(
    "/genres", status_code=status.HTTP_200_OK, response_model=NamedEntityListResponse
)
async def list_genres(db: DbSession, pagination: Pagination) -> NamedEntityListResponse:
    """List genres, ordered by id (public).

    Paginated: `page` starts at 1, `page_size` is 1-100 (default 20).
    A page past the end returns an empty `items` list.
    """
    genres, total = await list_named(
        db=db, model=Genre, page=pagination.page, page_size=pagination.page_size
    )
    return NamedEntityListResponse(
        items=[NamedEntityResponse.model_validate(genre) for genre in genres],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.get(
    "/genres/{genre_id}",
    status_code=status.HTTP_200_OK,
    response_model=NamedEntityResponse,
)
async def get_genre(db: DbSession, genre_id: int) -> Genre:
    """Get a genre by id (public). Returns 404 if it does not exist."""
    return await get_named(db=db, model=Genre, entity_id=genre_id)


@router.patch(
    "/genres/{genre_id}",
    response_model=NamedEntityResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(get_current_moderator)],
)
async def update_genre(db: DbSession, genre_id: int, data: NamedEntityRequest) -> Genre:
    """Rename a genre (moderator only).

    Returns 404 if the genre does not exist and 409 if another
    genre already has this name.
    """
    return await update_named(db=db, model=Genre, entity_id=genre_id, name=data.name)


@router.delete(
    "/genres/{genre_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(get_current_moderator)],
)
async def delete_genre(db: DbSession, genre_id: int) -> None:
    """Delete a genre (moderator only).

    The genre is also removed from all movies that had it; the movies
    themselves are kept. Returns 404 if the genre does not exist.
    """
    await delete_named(db=db, model=Genre, entity_id=genre_id)


@router.post(
    "/stars",
    response_model=NamedEntityResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(get_current_moderator)],
)
async def create_star(db: DbSession, data: NamedEntityRequest) -> Star:
    """Create a star (moderator only).

    Leading and trailing whitespace in the name is stripped.
    Returns 409 if a star with this name already exists.
    """
    return await create_named(db=db, model=Star, name=data.name)


@router.get(
    "/stars", status_code=status.HTTP_200_OK, response_model=NamedEntityListResponse
)
async def list_stars(db: DbSession, pagination: Pagination) -> NamedEntityListResponse:
    """List stars, ordered by id (public).

    Paginated: `page` starts at 1, `page_size` is 1-100 (default 20).
    A page past the end returns an empty `items` list.
    """
    stars, total = await list_named(
        db=db, model=Star, page=pagination.page, page_size=pagination.page_size
    )
    return NamedEntityListResponse(
        items=[NamedEntityResponse.model_validate(star) for star in stars],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.get(
    "/stars/{star_id}",
    status_code=status.HTTP_200_OK,
    response_model=NamedEntityResponse,
)
async def get_star(db: DbSession, star_id: int) -> Star:
    """Get a star by id (public). Returns 404 if it does not exist."""
    return await get_named(db=db, model=Star, entity_id=star_id)


@router.patch(
    "/stars/{star_id}",
    response_model=NamedEntityResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(get_current_moderator)],
)
async def update_star(db: DbSession, star_id: int, data: NamedEntityRequest) -> Star:
    """Rename a star (moderator only).

    Returns 404 if the star does not exist and 409 if another
    star already has this name.
    """
    return await update_named(db=db, model=Star, entity_id=star_id, name=data.name)


@router.delete(
    "/stars/{star_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(get_current_moderator)],
)
async def delete_star(db: DbSession, star_id: int) -> None:
    """Delete a star (moderator only).

    The star is also removed from all movies they appeared in; the movies
    themselves are kept. Returns 404 if the star does not exist.
    """
    await delete_named(db=db, model=Star, entity_id=star_id)


@router.post(
    "/directors",
    response_model=NamedEntityResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(get_current_moderator)],
)
async def create_director(db: DbSession, data: NamedEntityRequest) -> Director:
    """Create a director (moderator only).

    Leading and trailing whitespace in the name is stripped.
    Returns 409 if a director with this name already exists.
    """
    return await create_named(db=db, model=Director, name=data.name)


@router.get(
    "/directors",
    status_code=status.HTTP_200_OK,
    response_model=NamedEntityListResponse,
)
async def list_directors(
    db: DbSession, pagination: Pagination
) -> NamedEntityListResponse:
    """List directors, ordered by id (public).

    Paginated: `page` starts at 1, `page_size` is 1-100 (default 20).
    A page past the end returns an empty `items` list.
    """
    directors, total = await list_named(
        db=db, model=Director, page=pagination.page, page_size=pagination.page_size
    )
    return NamedEntityListResponse(
        items=[NamedEntityResponse.model_validate(director) for director in directors],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.get(
    "/directors/{director_id}",
    status_code=status.HTTP_200_OK,
    response_model=NamedEntityResponse,
)
async def get_director(db: DbSession, director_id: int) -> Director:
    """Get a director by id (public). Returns 404 if it does not exist."""
    return await get_named(db=db, model=Director, entity_id=director_id)


@router.patch(
    "/directors/{director_id}",
    response_model=NamedEntityResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(get_current_moderator)],
)
async def update_director(
    db: DbSession, director_id: int, data: NamedEntityRequest
) -> Director:
    """Rename a director (moderator only).

    Returns 404 if the director does not exist and 409 if another
    director already has this name.
    """
    return await update_named(
        db=db, model=Director, entity_id=director_id, name=data.name
    )


@router.delete(
    "/directors/{director_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(get_current_moderator)],
)
async def delete_director(db: DbSession, director_id: int) -> None:
    """Delete a director (moderator only).

    The director is also removed from all movies they directed; the movies
    themselves are kept. Returns 404 if the director does not exist.
    """
    await delete_named(db=db, model=Director, entity_id=director_id)


@router.post(
    "/certifications",
    response_model=NamedEntityResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(get_current_moderator)],
)
async def create_certification(
    db: DbSession, data: NamedEntityRequest
) -> Certification:
    """Create a certification (moderator only).

    Leading and trailing whitespace in the name is stripped.
    Returns 409 if a certification with this name already exists.
    """
    return await create_named(db=db, model=Certification, name=data.name)


@router.get(
    "/certifications",
    status_code=status.HTTP_200_OK,
    response_model=NamedEntityListResponse,
)
async def list_certifications(
    db: DbSession, pagination: Pagination
) -> NamedEntityListResponse:
    """List certifications, ordered by id (public).

    Paginated: `page` starts at 1, `page_size` is 1-100 (default 20).
    A page past the end returns an empty `items` list.
    """
    certifications, total = await list_named(
        db=db,
        model=Certification,
        page=pagination.page,
        page_size=pagination.page_size,
    )
    return NamedEntityListResponse(
        items=[
            NamedEntityResponse.model_validate(certification)
            for certification in certifications
        ],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.get(
    "/certifications/{certification_id}",
    status_code=status.HTTP_200_OK,
    response_model=NamedEntityResponse,
)
async def get_certification(db: DbSession, certification_id: int) -> Certification:
    """Get a certification by id (public). Returns 404 if it does not exist."""
    return await get_named(db=db, model=Certification, entity_id=certification_id)


@router.patch(
    "/certifications/{certification_id}",
    response_model=NamedEntityResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(get_current_moderator)],
)
async def update_certification(
    db: DbSession, certification_id: int, data: NamedEntityRequest
) -> Certification:
    """Rename a certification (moderator only).

    Movies keep referencing it under the new name. Returns 404 if the
    certification does not exist and 409 if another one already has this name.
    """
    return await update_named(
        db=db, model=Certification, entity_id=certification_id, name=data.name
    )


@router.delete(
    "/certifications/{certification_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(get_current_moderator)],
)
async def delete_certification(db: DbSession, certification_id: int) -> None:
    """Delete a certification (moderator only).

    Returns 409 if any movie still uses it: reassign those movies to another
    certification first. Returns 404 if the certification does not exist.
    """
    await delete_named(db=db, model=Certification, entity_id=certification_id)


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
    response_model=MovieResponse,
    status_code=status.HTTP_200_OK,
)
async def get_movie_detail(db: DbSession, movie_id: int) -> MovieResponse:
    """Get a movie with its certification, genres, directors and stars (public).

    `poster_url` is a temporary link (valid for 1 hour) or null.
    Returns 404 if the movie does not exist.
    """
    movie = await get_movie(db=db, movie_id=movie_id)
    return _to_movie_response(movie)


def _to_movie_list_item(movie: Movie) -> MovieListItemResponse:
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
        items=[_to_movie_list_item(movie) for movie in movies],
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
    """Delete a movie and movie poster(moderator only).

    Its links to genres, directors and stars are removed as well;
    the catalog entities themselves are kept.
    Returns 404 if the movie does not exist.
    """
    await delete_movie(db=db, movie_id=movie_id)


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
