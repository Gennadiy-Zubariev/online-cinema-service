from fastapi import APIRouter, Depends, status

from src.accounts.dependencies import get_current_moderator
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
)

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


@router.post(
    "/movies",
    response_model=MovieResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(get_current_moderator)],
)
async def add_movie(db: DbSession, data: MovieCreateRequest) -> Movie:
    """Create a movie (moderator only).

    Catalog entities are referenced by id: `certification_id` is required,
    `genre_ids`, `director_ids` and `star_ids` are optional (duplicates are ignored).
    Returns 404 if any referenced entity does not exist.
    Returns 409 if a movie with the same name, year and duration already exists.
    """
    return await create_movie(db=db, data=data)


@router.patch(
    "/movies/{movie_id}",
    response_model=MovieResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(get_current_moderator)],
)
async def edit_movie(db: DbSession, movie_id: int, data: MovieUpdateRequest) -> Movie:
    """Partially update a movie (moderator only).

    Only the fields sent are changed; `meta_score` and `gross` can be cleared
    with null, other fields cannot be null. A list of ids (`genre_ids`, ...)
    replaces the current set; send [] to remove all.
    Returns 404 if the movie or any referenced entity does not exist.
    Returns 409 if another movie has the same name, year and duration.
    """
    return await update_movie(db=db, movie_id=movie_id, data=data)


@router.delete(
    "/movies/{movie_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(get_current_moderator)],
)
async def remove_movie(db: DbSession, movie_id: int) -> None:
    """Delete a movie (moderator only).

    Its links to genres, directors and stars are removed as well;
    the catalog entities themselves are kept.
    Returns 404 if the movie does not exist.
    """
    await delete_movie(db=db, movie_id=movie_id)
