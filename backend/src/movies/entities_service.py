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
from src.movies.models import Genre, Star, Director, Certification, movie_genres

NamedModel = TypeVar("NamedModel", Genre, Star, Director, Certification)


async def commit_unique(db: AsyncSession, model: type[Base]) -> None:
    """Commit; turn a unique violation into EntityAlreadyExistsError(model name).

    Other integrity errors are re-raised (a 500 shows a real bug).
    No SELECT beforehand: it would not close the race anyway.
    """
    try:
        await db.commit()
    except IntegrityError as error:
        await db.rollback()
        if isinstance(error.orig, UniqueViolation):
            raise EntityAlreadyExistsError(model.__name__) from error
        raise


async def create_named(
    db: AsyncSession, model: type[NamedModel], name: str
) -> NamedModel:
    """Create a genre / star / director / certification.

    Raises EntityAlreadyExistsError for a duplicate name.
    """
    entity = model(name=name)
    db.add(entity)
    await commit_unique(db=db, model=model)
    return entity


async def list_named(
    db: AsyncSession, model: type[NamedModel], page: int, page_size: int
) -> tuple[list[NamedModel], int]:
    """Return (entities on the page ordered by id, total count)."""
    total = await db.scalar(select(func.count()).select_from(model))
    result = await db.scalars(
        select(model).order_by(model.id).offset((page - 1) * page_size).limit(page_size)
    )
    return list(result.all()), total or 0


async def get_named(
    db: AsyncSession, model: type[NamedModel], entity_id: int
) -> NamedModel:
    """Return an entity by id; raises EntityNotFoundError."""
    entity = await db.get(model, entity_id)
    if entity is None:
        raise EntityNotFoundError(model.__name__)
    return entity


async def update_named(
    db: AsyncSession, model: type[NamedModel], entity_id: int, name: str
) -> NamedModel:
    """Rename an entity; raises EntityNotFoundError or EntityAlreadyExistsError."""
    entity = await get_named(db=db, model=model, entity_id=entity_id)
    entity.name = name
    await commit_unique(db=db, model=model)
    return entity


async def delete_named(
    db: AsyncSession, model: type[NamedModel], entity_id: int
) -> None:
    """Delete an entity; raises EntityNotFoundError.

    Movie links of genres / stars / directors are removed by ON DELETE CASCADE.
    A certification used by movies is protected by RESTRICT: the foreign key
    violation becomes EntityInUseError (409).
    """
    entity = await get_named(db=db, model=model, entity_id=entity_id)
    await db.delete(entity)
    try:
        await db.commit()
    except IntegrityError as error:
        await db.rollback()
        if isinstance(error.orig, ForeignKeyViolation):
            raise EntityInUseError(model.__name__) from error
        raise


async def list_genres_with_movie_count(
    db: AsyncSession, page: int, page_size: int
) -> tuple[list[tuple[Genre, int]], int]:
    """Return ((genre, movie count) pairs on the page, total number of genres).

    LEFT JOIN + count(column), so genres without movies are listed with 0.
    """
    total = await db.scalar(select(func.count()).select_from(Genre))
    result = await db.execute(
        select(Genre, func.count(movie_genres.c.movie_id))
        .outerjoin(movie_genres, movie_genres.c.genre_id == Genre.id)
        .group_by(Genre.id)
        .order_by(Genre.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return [(genre, count) for genre, count in result.all()], total or 0
