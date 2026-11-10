"""Shared fixtures and helpers for movies integration tests."""

from dataclasses import dataclass
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.accounts.models import User, UserGroupEnum
from src.accounts.security import create_access_token
from src.config.settings import get_settings
from src.movies.models import Certification, Director, Genre, Movie, Star
from tests.integration.conftest import CreateUser

MOVIES_URL = "/api/v1/movies"
PERMISSION_DENIED = {"detail": "You do not have permission to perform this action."}
UNKNOWN_ID = 999999


@dataclass(frozen=True)
class Catalog:
    certification: Certification
    genres: list[Genre]
    director: Director
    star: Star


@pytest.fixture
async def catalog(db_session: AsyncSession) -> Catalog:
    """Lookup entities a movie can reference."""
    result = Catalog(
        certification=Certification(name="PG-13"),
        genres=[Genre(name="Drama"), Genre(name="Comedy")],
        director=Director(name="Christopher Nolan"),
        star=Star(name="Cillian Murphy"),
    )
    db_session.add_all(
        [result.certification, *result.genres, result.director, result.star]
    )
    await db_session.commit()
    return result


@pytest.fixture
async def movie(db_session: AsyncSession, catalog: Catalog) -> Movie:
    """Saved movie linked to the first genre, the director and the star."""
    result = Movie(
        name="Inception",
        year=2010,
        time=148,
        imdb=8.8,
        votes=2500000,
        meta_score=74,
        gross=292000000,
        description="A thief who steals corporate secrets through dreams.",
        price=Decimal("7.99"),
        certification=catalog.certification,
        genres=[catalog.genres[0]],
        directors=[catalog.director],
        stars=[catalog.star],
    )
    db_session.add(result)
    await db_session.commit()
    return result


def movie_url(movie_id: int) -> str:
    return f"{MOVIES_URL}/{movie_id}"


def auth_header(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user.id, get_settings())}"}


async def create_caller(
    create_user: CreateUser, group: UserGroupEnum = UserGroupEnum.MODERATOR
) -> User:
    return await create_user(is_active=True, token_expires_in=None, group=group)
