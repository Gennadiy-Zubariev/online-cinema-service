from typing import TypeVar

from psycopg.errors import UniqueViolation, ForeignKeyViolation
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.base import Base
from src.movies.exceptions import (
    EntityAlreadyExistsError,
    EntityNotFoundError,
    EntityInUseError,
)
from src.movies.models import Genre, Star, Director, Certification, Movie
from src.movies.schemas import MovieCreateRequest

NamedModel = TypeVar("NamedModel", Genre, Star, Director, Certification)


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
        **data.model_dump(
            exclude={"certification_id", "genre_ids", "director_ids", "star_ids"}
        ),
        certification=certification,
        genres=genres,
        directors=directors,
        stars=stars,
    )
    db.add(movie)
    await _commit_unique(db=db, model=Movie)
    return movie
