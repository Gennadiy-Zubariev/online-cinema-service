from uuid import uuid4

from psycopg.errors import ForeignKeyViolation
from sqlalchemy import select, func, or_, Select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload
from starlette.concurrency import run_in_threadpool

from src.movies.entities_service import NamedModel, commit_unique, get_named
from src.movies.exceptions import EntityNotFoundError, EntityInUseError
from src.movies.models import Genre, Star, Director, Certification, Movie
from src.movies.schemas import (
    MovieCreateRequest,
    MovieUpdateRequest,
    MovieCatalogQuery,
)
from src.storage.client import upload_file, delete_file
from src.storage.images import validate_image

RELATION_ID_FIELDS = {"certification_id", "genre_ids", "director_ids", "star_ids"}
MAX_POSTER_SIZE = 5 * 1024 * 1024  # 5 MB
SORT_COLUMNS = {
    "id": Movie.id,
    "price": Movie.price,
    "year": Movie.year,
    "votes": Movie.votes,
}


async def _get_named_by_ids(
    db: AsyncSession, model: type[NamedModel], ids: set[int]
) -> list[NamedModel]:
    """Load entities by ids in one query; raise EntityNotFoundError if any is missing.

    An empty set returns [] without a query.
    """
    if not ids:
        return []
    result = await db.scalars(select(model).where(model.id.in_(ids)))
    entities = list(result.all())
    if len(entities) != len(ids):
        raise EntityNotFoundError(model.__name__)
    return entities


async def list_catalog_movies(
    db: AsyncSession,
    stmt: Select[Movie],
    params: MovieCatalogQuery,
    page: int,
    page_size: int,
) -> tuple[list[Movie], int]:
    """Apply catalog filters, search, sorting and pagination to a base query.

    Shared by the catalog, favorites and purchased movies, so all three behave
    the same. Returns (movies with genres loaded, total matching the filters).
    Search uses EXISTS for stars / directors (no duplicate movies); id is the
    second sort key to keep pages stable.
    """
    if params.year_from is not None:
        stmt = stmt.where(Movie.year >= params.year_from)
    if params.year_to is not None:
        stmt = stmt.where(Movie.year <= params.year_to)
    if params.imdb_min is not None:
        stmt = stmt.where(Movie.imdb >= params.imdb_min)
    if params.imdb_max is not None:
        stmt = stmt.where(Movie.imdb <= params.imdb_max)
    if params.genre_id is not None:
        stmt = stmt.where(Movie.genres.any(Genre.id == params.genre_id))
    if params.search:
        stmt = stmt.where(
            or_(
                Movie.name.icontains(params.search, autoescape=True),
                Movie.description.icontains(params.search, autoescape=True),
                Movie.stars.any(Star.name.icontains(params.search, autoescape=True)),
                Movie.directors.any(
                    Director.name.icontains(params.search, autoescape=True)
                ),
            )
        )
    column = SORT_COLUMNS[params.sort_by]
    sort = column.desc() if params.order == "desc" else column.asc()
    total = await db.scalar(select(func.count()).select_from(stmt.subquery()))
    result = await db.scalars(
        stmt.options(selectinload(Movie.genres))
        .order_by(sort, Movie.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(result.all()), total or 0


async def create_movie(
    db: AsyncSession,
    data: MovieCreateRequest,
) -> Movie:
    """Create a movie with its certification, genres, directors and stars.

    Raises EntityNotFoundError for an unknown related id and
    EntityAlreadyExistsError for a duplicate (name, year, time).
    """
    certification = await get_named(
        db=db, model=Certification, entity_id=data.certification_id
    )
    genres = await _get_named_by_ids(db=db, model=Genre, ids=data.genre_ids)
    directors = await _get_named_by_ids(db=db, model=Director, ids=data.director_ids)
    stars = await _get_named_by_ids(db=db, model=Star, ids=data.star_ids)
    movie = Movie(
        **data.model_dump(exclude=RELATION_ID_FIELDS),
        certification=certification,
        genres=genres,
        directors=directors,
        stars=stars,
    )
    db.add(movie)
    await commit_unique(db=db, model=Movie)
    return movie


async def get_movie(db: AsyncSession, movie_id: int) -> Movie:
    """Return a movie with all relationships loaded; raises EntityNotFoundError."""
    movie = await db.scalar(
        select(Movie)
        .where(Movie.id == movie_id)
        .options(
            joinedload(Movie.certification),
            selectinload(Movie.genres),
            selectinload(Movie.stars),
            selectinload(Movie.directors),
        )
    )
    if movie is None:
        raise EntityNotFoundError(Movie.__name__)
    return movie


async def list_movies(
    db: AsyncSession, params: MovieCatalogQuery, page: int, page_size: int
) -> tuple[list[Movie], int]:
    """Return (catalog page, total) for the public catalog."""
    return await list_catalog_movies(
        db=db, stmt=select(Movie), params=params, page=page, page_size=page_size
    )


async def update_movie(
    db: AsyncSession, movie_id: int, data: MovieUpdateRequest
) -> Movie:
    """Partially update a movie; id lists replace the related sets.

    All related entities are loaded before setattr: otherwise autoflush sends
    the UPDATE early and a duplicate escapes commit_unique as a 500.
    Raises EntityNotFoundError / EntityAlreadyExistsError.
    """
    movie = await get_movie(db=db, movie_id=movie_id)

    if data.certification_id is not None:
        movie.certification = await get_named(
            db=db, model=Certification, entity_id=data.certification_id
        )
    if data.genre_ids is not None:
        movie.genres = await _get_named_by_ids(db=db, model=Genre, ids=data.genre_ids)
    if data.director_ids is not None:
        movie.directors = await _get_named_by_ids(
            db=db, model=Director, ids=data.director_ids
        )
    if data.star_ids is not None:
        movie.stars = await _get_named_by_ids(db=db, model=Star, ids=data.star_ids)

    for field, value in data.model_dump(
        exclude_unset=True, exclude=RELATION_ID_FIELDS
    ).items():
        setattr(movie, field, value)

    await commit_unique(db=db, model=Movie)
    return movie


async def delete_movie(db: AsyncSession, movie_id: int) -> None:
    """Delete a movie, then its poster file.

    Raises EntityNotFoundError, or EntityInUseError (409) if the movie is in
    an order or purchased (RESTRICT). The poster is deleted only after commit.
    """
    movie = await db.get(Movie, movie_id)
    if movie is None:
        raise EntityNotFoundError(Movie.__name__)
    poster_key = movie.poster
    await db.delete(movie)
    try:
        await db.commit()
    except IntegrityError as error:
        await db.rollback()
        if isinstance(error.orig, ForeignKeyViolation):
            raise EntityInUseError(Movie.__name__) from error
        raise
    if poster_key is not None:
        await run_in_threadpool(delete_file, poster_key)


async def update_movie_poster(
    db: AsyncSession, movie_id: int, data: bytes, content_type: str | None
) -> Movie:
    """Validate and upload a new poster, then delete the old file.

    The image is validated before the DB lookup. Order upload -> commit ->
    delete old: a failure leaves at most an orphan file in S3.
    """
    content_type, extension = validate_image(data, content_type, MAX_POSTER_SIZE)
    movie = await get_movie(db=db, movie_id=movie_id)

    old_key = movie.poster
    new_key = f"posters/{movie_id}/{uuid4().hex}.{extension}"
    await run_in_threadpool(upload_file, new_key, data, content_type)
    movie.poster = new_key
    await db.commit()

    if old_key is not None:
        await run_in_threadpool(delete_file, old_key)
    return movie
