from typing import TypeVar
from uuid import uuid4

from psycopg.errors import UniqueViolation, ForeignKeyViolation
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload
from starlette.concurrency import run_in_threadpool

from src.database.base import Base
from src.movies.exceptions import (
    EntityAlreadyExistsError,
    EntityNotFoundError,
    EntityInUseError,
)
from src.movies.models import Genre, Star, Director, Certification, Movie
from src.movies.schemas import MovieCreateRequest, MovieUpdateRequest
from src.storage.client import upload_file, delete_file
from src.storage.images import validate_image

NamedModel = TypeVar("NamedModel", Genre, Star, Director, Certification)
RELATION_ID_FIELDS = {"certification_id", "genre_ids", "director_ids", "star_ids"}
MAX_POSTER_SIZE = 5 * 1024 * 1024  # 5 MB


async def _commit_unique(db: AsyncSession, model: type[Base]) -> None:
    try:
        await db.commit()
    except IntegrityError as error:
        await db.rollback()
        if isinstance(error.orig, UniqueViolation):
            raise EntityAlreadyExistsError(model.__name__) from error
        raise


async def _get_named_by_ids(
    db: AsyncSession, model: type[NamedModel], ids: set[int]
) -> list[NamedModel]:
    if not ids:
        return []
    result = await db.scalars(select(model).where(model.id.in_(ids)))
    entities = list(result.all())
    if len(entities) != len(ids):
        raise EntityNotFoundError(model.__name__)
    return entities


async def create_named(
    db: AsyncSession, model: type[NamedModel], name: str
) -> NamedModel:
    entity = model(name=name)
    db.add(entity)
    await _commit_unique(db=db, model=model)
    return entity


async def list_named(
    db: AsyncSession, model: type[NamedModel], page: int, page_size: int
) -> tuple[list[NamedModel], int]:
    total = await db.scalar(select(func.count()).select_from(model))
    result = await db.scalars(
        select(model).order_by(model.id).offset((page - 1) * page_size).limit(page_size)
    )
    return list(result.all()), total or 0


async def get_named(
    db: AsyncSession, model: type[NamedModel], entity_id: int
) -> NamedModel:
    entity = await db.get(model, entity_id)
    if entity is None:
        raise EntityNotFoundError(model.__name__)
    return entity


async def update_named(
    db: AsyncSession, model: type[NamedModel], entity_id: int, name: str
) -> NamedModel:
    entity = await get_named(db=db, model=model, entity_id=entity_id)
    entity.name = name
    await _commit_unique(db=db, model=model)
    return entity


async def delete_named(
    db: AsyncSession, model: type[NamedModel], entity_id: int
) -> None:
    entity = await get_named(db=db, model=model, entity_id=entity_id)
    await db.delete(entity)
    try:
        await db.commit()
    except IntegrityError as error:
        await db.rollback()
        if isinstance(error.orig, ForeignKeyViolation):
            raise EntityInUseError(model.__name__) from error
        raise


async def create_movie(
    db: AsyncSession,
    data: MovieCreateRequest,
) -> Movie:
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
    await _commit_unique(db=db, model=Movie)
    return movie


async def get_movie(db: AsyncSession, movie_id: int) -> Movie:
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


async def update_movie(
    db: AsyncSession, movie_id: int, data: MovieUpdateRequest
) -> Movie:
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

    await _commit_unique(db=db, model=Movie)
    return movie


async def delete_movie(db: AsyncSession, movie_id: int) -> None:
    movie = await db.get(Movie, movie_id)
    if movie is None:
        raise EntityNotFoundError(Movie.__name__)
    await db.delete(movie)
    await db.commit()


async def update_movie_poster(
    db: AsyncSession, movie_id: int, data: bytes, content_type: str | None
) -> Movie:
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
