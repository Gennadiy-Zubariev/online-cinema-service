from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.accounts.models import ActivationToken, User, UserGroup, UserGroupEnum
from src.accounts.security import create_access_token, hash_password, hash_token
from src.config.settings import get_settings
from src.movies.models import Certification, Director, Genre, Movie, Star

RAW_ACTIVATION_TOKEN = "raw-activation-token"
USER_PASSWORD = "StrongPass1!"

CreateUser = Callable[..., Awaitable[User]]


@pytest.fixture
def create_user(db_session: AsyncSession) -> CreateUser:
    """Factory: save a user (optionally with an activation token) directly in DB.

    Bypasses the register endpoint, so tests control `is_active` and token expiry.
    The password is always `USER_PASSWORD` (real argon2 hash, so login works).
    `token_expires_in=None` creates the user without an activation token.
    """

    async def _create_user(
        email: str = "user@example.com",
        is_active: bool = False,
        token_expires_in: timedelta | None = timedelta(hours=24),
        group: UserGroupEnum = UserGroupEnum.USER,
    ) -> User:
        user_group = await db_session.scalar(
            select(UserGroup).where(UserGroup.name == group)
        )
        user = User(
            email=email,
            hashed_password=hash_password(USER_PASSWORD),
            is_active=is_active,
            group=user_group,
        )
        if token_expires_in is not None:
            user.activation_token = ActivationToken(
                token_hash=hash_token(RAW_ACTIVATION_TOKEN),
                expires_at=datetime.now(UTC) + token_expires_in,
            )
        db_session.add(user)
        await db_session.commit()
        return user

    return _create_user


# --- shared by movies and cart tests ---

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


def auth_header(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user.id, get_settings())}"}


async def create_caller(
    create_user: CreateUser, group: UserGroupEnum = UserGroupEnum.MODERATOR
) -> User:
    return await create_user(is_active=True, token_expires_in=None, group=group)
