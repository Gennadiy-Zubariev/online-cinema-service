"""Movie CRUD (moderator): create.

Catalog entities are referenced by id; the response nests them as {id, name}.
"""

from dataclasses import dataclass
from typing import Any
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.accounts.models import User, UserGroupEnum
from src.accounts.security import create_access_token
from src.config.settings import get_settings
from src.movies.models import (
    Certification,
    Director,
    Genre,
    Movie,
    Star,
    movie_genres,
)
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


def auth_header(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user.id, get_settings())}"}


async def create_caller(
    create_user: CreateUser, group: UserGroupEnum = UserGroupEnum.MODERATOR
) -> User:
    return await create_user(is_active=True, token_expires_in=None, group=group)


def movie_payload(catalog: Catalog, **overrides: Any) -> dict[str, Any]:
    """Valid create body referencing every entity of `catalog`."""
    payload: dict[str, Any] = {
        "name": "Oppenheimer",
        "year": 2023,
        "time": 180,
        "imdb": 8.3,
        "votes": 900000,
        "meta_score": 90,
        "gross": 330000000,
        "description": "The story of J. Robert Oppenheimer.",
        "price": "9.99",
        "certification_id": catalog.certification.id,
        "genre_ids": [genre.id for genre in catalog.genres],
        "director_ids": [catalog.director.id],
        "star_ids": [catalog.star.id],
    }
    payload.update(overrides)
    return payload


def sorted_by_id(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(items, key=lambda item: item["id"])


# --- access control ---


async def test_create_requires_token(client: AsyncClient, catalog: Catalog) -> None:
    response = await client.post(MOVIES_URL, json=movie_payload(catalog))

    assert response.status_code == 401


async def test_create_rejects_regular_user(
    client: AsyncClient, create_user: CreateUser, catalog: Catalog
) -> None:
    caller = await create_caller(create_user, group=UserGroupEnum.USER)

    response = await client.post(
        MOVIES_URL, json=movie_payload(catalog), headers=auth_header(caller)
    )

    assert response.status_code == 403
    assert response.json() == PERMISSION_DENIED


@pytest.mark.parametrize("group", [UserGroupEnum.MODERATOR, UserGroupEnum.ADMIN])
async def test_moderator_and_admin_can_create(
    client: AsyncClient,
    create_user: CreateUser,
    catalog: Catalog,
    group: UserGroupEnum,
) -> None:
    caller = await create_caller(create_user, group=group)

    response = await client.post(
        MOVIES_URL, json=movie_payload(catalog), headers=auth_header(caller)
    )

    assert response.status_code == 201


# --- create ---


async def test_create(
    client: AsyncClient,
    create_user: CreateUser,
    db_session: AsyncSession,
    catalog: Catalog,
) -> None:
    caller = await create_caller(create_user)

    response = await client.post(
        MOVIES_URL, json=movie_payload(catalog), headers=auth_header(caller)
    )

    assert response.status_code == 201
    body = response.json()
    UUID(body["uuid"])  # valid UUID string
    assert body["name"] == "Oppenheimer"
    assert body["year"] == 2023
    assert body["time"] == 180
    assert body["imdb"] == 8.3
    assert body["votes"] == 900000
    assert body["meta_score"] == 90
    assert body["gross"] == 330000000
    assert body["description"] == "The story of J. Robert Oppenheimer."
    assert body["price"] == "9.99"
    assert body["certification"] == {"id": catalog.certification.id, "name": "PG-13"}
    assert sorted_by_id(body["genres"]) == sorted_by_id(
        [{"id": genre.id, "name": genre.name} for genre in catalog.genres]
    )
    assert body["directors"] == [
        {"id": catalog.director.id, "name": "Christopher Nolan"}
    ]
    assert body["stars"] == [{"id": catalog.star.id, "name": "Cillian Murphy"}]

    stored_genre_links = await db_session.scalar(
        select(func.count())
        .select_from(movie_genres)
        .where(movie_genres.c.movie_id == body["id"])
    )
    assert stored_genre_links == 2


async def test_create_with_certification_only(
    client: AsyncClient, create_user: CreateUser, catalog: Catalog
) -> None:
    caller = await create_caller(create_user)
    payload = movie_payload(catalog, meta_score=None, gross=None)
    for field in ("genre_ids", "director_ids", "star_ids"):
        del payload[field]

    response = await client.post(MOVIES_URL, json=payload, headers=auth_header(caller))

    assert response.status_code == 201
    body = response.json()
    assert body["genres"] == []
    assert body["directors"] == []
    assert body["stars"] == []
    assert body["meta_score"] is None
    assert body["gross"] is None


async def test_create_ignores_duplicate_ids(
    client: AsyncClient, create_user: CreateUser, catalog: Catalog
) -> None:
    caller = await create_caller(create_user)
    genre_id = catalog.genres[0].id

    response = await client.post(
        MOVIES_URL,
        json=movie_payload(catalog, genre_ids=[genre_id, genre_id]),
        headers=auth_header(caller),
    )

    assert response.status_code == 201
    assert response.json()["genres"] == [{"id": genre_id, "name": "Drama"}]


async def test_create_strips_name(
    client: AsyncClient, create_user: CreateUser, catalog: Catalog
) -> None:
    caller = await create_caller(create_user)

    response = await client.post(
        MOVIES_URL,
        json=movie_payload(catalog, name="  Oppenheimer  "),
        headers=auth_header(caller),
    )

    assert response.status_code == 201
    assert response.json()["name"] == "Oppenheimer"


@pytest.mark.parametrize(
    ("field", "entity"),
    [
        ("certification_id", "Certification"),
        ("genre_ids", "Genre"),
        ("director_ids", "Director"),
        ("star_ids", "Star"),
    ],
    ids=["certification", "genre", "director", "star"],
)
async def test_create_with_unknown_entity_returns_404(
    client: AsyncClient,
    create_user: CreateUser,
    db_session: AsyncSession,
    catalog: Catalog,
    field: str,
    entity: str,
) -> None:
    caller = await create_caller(create_user)
    payload = movie_payload(catalog)
    if field == "certification_id":
        payload[field] = UNKNOWN_ID
    else:
        # one valid id + one unknown: a partial match must still be rejected
        payload[field] = [*payload[field], UNKNOWN_ID]

    response = await client.post(MOVIES_URL, json=payload, headers=auth_header(caller))

    assert response.status_code == 404
    assert response.json() == {"detail": f"{entity} not found."}
    assert await db_session.scalar(select(func.count()).select_from(Movie)) == 0


async def test_create_duplicate_returns_409(
    client: AsyncClient,
    create_user: CreateUser,
    db_session: AsyncSession,
    catalog: Catalog,
) -> None:
    caller = await create_caller(create_user)
    await client.post(
        MOVIES_URL, json=movie_payload(catalog), headers=auth_header(caller)
    )

    response = await client.post(
        MOVIES_URL, json=movie_payload(catalog), headers=auth_header(caller)
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "Movie already exists."}
    assert await db_session.scalar(select(func.count()).select_from(Movie)) == 1


@pytest.mark.parametrize(
    "overrides",
    [{"year": 2024}, {"time": 181}],
    ids=["other_year", "other_time"],
)
async def test_create_same_name_differing_in_year_or_time(
    client: AsyncClient,
    create_user: CreateUser,
    catalog: Catalog,
    overrides: dict[str, int],
) -> None:
    caller = await create_caller(create_user)
    await client.post(
        MOVIES_URL, json=movie_payload(catalog), headers=auth_header(caller)
    )

    response = await client.post(
        MOVIES_URL,
        json=movie_payload(catalog, **overrides),
        headers=auth_header(caller),
    )

    assert response.status_code == 201


@pytest.mark.parametrize(
    "overrides",
    [
        {"name": ""},
        {"name": "a" * 256},
        {"description": "   "},
        {"year": 1887},
        {"time": 0},
        {"imdb": 10.1},
        {"imdb": -0.1},
        {"votes": -1},
        {"meta_score": 101},
        {"gross": -1},
        {"price": "9.999"},
        {"price": "-1"},
        {"price": "123456789.00"},
        {"certification_id": None},
        {"genre_ids": ["abc"]},
    ],
    ids=[
        "empty_name",
        "name_too_long",
        "blank_description",
        "year_too_early",
        "zero_time",
        "imdb_above_10",
        "imdb_negative",
        "negative_votes",
        "meta_score_above_100",
        "negative_gross",
        "price_three_decimals",
        "negative_price",
        "price_too_many_digits",
        "missing_certification",
        "non_int_genre_id",
    ],
)
async def test_create_invalid_body_returns_422(
    client: AsyncClient,
    create_user: CreateUser,
    catalog: Catalog,
    overrides: dict[str, Any],
) -> None:
    caller = await create_caller(create_user)

    response = await client.post(
        MOVIES_URL,
        json=movie_payload(catalog, **overrides),
        headers=auth_header(caller),
    )

    assert response.status_code == 422
