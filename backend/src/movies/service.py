from typing import TypeVar

from psycopg.errors import UniqueViolation
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.movies.exceptions import EntityAlreadyExistsError
from src.movies.models import Genre, Star, Director, Certification

NamedModel = TypeVar("NamedModel", Genre, Star, Director, Certification)


async def create_named(
    db: AsyncSession, model: type[NamedModel], name: str
) -> NamedModel:
    entity = model(name=name)
    db.add(entity)
    try:
        await db.commit()
    except IntegrityError as error:
        await db.rollback()
        if isinstance(error.orig, UniqueViolation):
            raise EntityAlreadyExistsError(model.__name__) from error
        raise
    return entity
