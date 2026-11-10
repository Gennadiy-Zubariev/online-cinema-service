"""CRUD of the catalog lookup tables: genres, stars, directors, certifications.

All four share the same service functions and schemas, so every common test
runs once per entity (the `entity` fixture is parametrized). Deletion differs:
genres/stars/directors are unlinked from movies (CASCADE on the association
table), a certification used by a movie cannot be deleted (RESTRICT -> 409).
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import Table, func, select
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
    movie_directors,
    movie_genres,
    movie_stars,
)
from tests.integration.conftest import CreateUser

PERMISSION_DENIED = {"detail": "You do not have permission to perform this action."}

CatalogModel = type[Genre] | type[Star] | type[Director] | type[Certification]


@dataclass(frozen=True)
class CatalogEntity:
    url: str
    model: CatalogModel

    @property
    def not_found(self) -> dict[str, str]:
        return {"detail": f"{self.model.__name__} not found."}

    @property
    def already_exists(self) -> dict[str, str]:
        return {"detail": f"{self.model.__name__} already exists."}


GENRES = CatalogEntity("/api/v1/genres", Genre)
STARS = CatalogEntity("/api/v1/stars", Star)
DIRECTORS = CatalogEntity("/api/v1/directors", Director)
CERTIFICATIONS = CatalogEntity("/api/v1/certifications", Certification)


@pytest.fixture(
    params=[GENRES, STARS, DIRECTORS, CERTIFICATIONS],
    ids=["genres", "stars", "directors", "certifications"],
)
def entity(request: pytest.FixtureRequest) -> CatalogEntity:
    result: CatalogEntity = request.param
    return result


def auth_header(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user.id, get_settings())}"}


async def create_caller(
    create_user: CreateUser, group: UserGroupEnum = UserGroupEnum.MODERATOR
) -> User:
    return await create_user(is_active=True, token_expires_in=None, group=group)


async def create_entity(
    db_session: AsyncSession, model: CatalogModel, name: str
) -> Any:
    instance = model(name=name)
    db_session.add(instance)
    await db_session.commit()
    return instance


async def create_movie(
    db_session: AsyncSession, *, name: str = "Test Movie", **relations: Any
) -> Movie:
    """Save a movie; `relations` sets certification/genres/stars/directors."""
    relations.setdefault("certification", Certification(name="PG-13"))
    movie = Movie(
        name=name,
        year=2020,
        time=120,
        imdb=7.5,
        votes=1000,
        description="Description.",
        price=Decimal("9.99"),
        **relations,
    )
    db_session.add(movie)
    await db_session.commit()
    return movie


# --- access control ---

WRITE_ENDPOINTS = [
    ("POST", "", {"name": "Drama"}),
    ("PATCH", "/{entity_id}", {"name": "Drama"}),
    ("DELETE", "/{entity_id}", None),
]
WRITE_IDS = ["create", "update", "delete"]


@pytest.mark.parametrize(("method", "path", "body"), WRITE_ENDPOINTS, ids=WRITE_IDS)
async def test_write_endpoints_reject_regular_user(
    client: AsyncClient,
    create_user: CreateUser,
    db_session: AsyncSession,
    entity: CatalogEntity,
    method: str,
    path: str,
    body: dict[str, str] | None,
) -> None:
    instance = await create_entity(db_session, entity.model, "Comedy")
    caller = await create_caller(create_user, group=UserGroupEnum.USER)

    response = await client.request(
        method,
        entity.url + path.format(entity_id=instance.id),
        json=body,
        headers=auth_header(caller),
    )

    assert response.status_code == 403
    assert response.json() == PERMISSION_DENIED


@pytest.mark.parametrize(("method", "path", "body"), WRITE_ENDPOINTS, ids=WRITE_IDS)
async def test_write_endpoints_require_token(
    client: AsyncClient,
    entity: CatalogEntity,
    method: str,
    path: str,
    body: dict[str, str] | None,
) -> None:
    response = await client.request(
        method, entity.url + path.format(entity_id=1), json=body
    )

    assert response.status_code == 401


@pytest.mark.parametrize("group", [UserGroupEnum.MODERATOR, UserGroupEnum.ADMIN])
async def test_moderator_and_admin_can_create(
    client: AsyncClient,
    create_user: CreateUser,
    entity: CatalogEntity,
    group: UserGroupEnum,
) -> None:
    caller = await create_caller(create_user, group=group)

    response = await client.post(
        entity.url, json={"name": "Drama"}, headers=auth_header(caller)
    )

    assert response.status_code == 201


async def test_read_endpoints_are_public(
    client: AsyncClient, db_session: AsyncSession, entity: CatalogEntity
) -> None:
    instance = await create_entity(db_session, entity.model, "Comedy")

    list_response = await client.get(entity.url)
    detail_response = await client.get(f"{entity.url}/{instance.id}")

    assert list_response.status_code == 200
    assert detail_response.status_code == 200


# --- create ---


async def test_create(
    client: AsyncClient,
    create_user: CreateUser,
    db_session: AsyncSession,
    entity: CatalogEntity,
) -> None:
    caller = await create_caller(create_user)

    response = await client.post(
        entity.url, json={"name": "  Drama  "}, headers=auth_header(caller)
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Drama"
    stored_name = await db_session.scalar(
        select(entity.model.name).where(entity.model.id == body["id"])
    )
    assert stored_name == "Drama"


async def test_create_duplicate_returns_409(
    client: AsyncClient,
    create_user: CreateUser,
    db_session: AsyncSession,
    entity: CatalogEntity,
) -> None:
    await create_entity(db_session, entity.model, "Drama")
    caller = await create_caller(create_user)

    response = await client.post(
        entity.url, json={"name": "Drama"}, headers=auth_header(caller)
    )

    assert response.status_code == 409
    assert response.json() == entity.already_exists


async def test_create_max_length_name(
    client: AsyncClient, create_user: CreateUser, entity: CatalogEntity
) -> None:
    caller = await create_caller(create_user)

    response = await client.post(
        entity.url, json={"name": "a" * 255}, headers=auth_header(caller)
    )

    assert response.status_code == 201


@pytest.mark.parametrize(
    "body",
    [{}, {"name": ""}, {"name": "   "}, {"name": "a" * 256}],
    ids=["missing", "empty", "whitespace", "too_long"],
)
async def test_create_invalid_name_returns_422(
    client: AsyncClient,
    create_user: CreateUser,
    entity: CatalogEntity,
    body: dict[str, str],
) -> None:
    caller = await create_caller(create_user)

    response = await client.post(entity.url, json=body, headers=auth_header(caller))

    assert response.status_code == 422


# --- list ---


async def test_list_ordered_by_id(
    client: AsyncClient, db_session: AsyncSession, entity: CatalogEntity
) -> None:
    first = await create_entity(db_session, entity.model, "Drama")
    second = await create_entity(db_session, entity.model, "Action")

    response = await client.get(entity.url)

    assert response.status_code == 200
    body = response.json()
    # genres also have `movies_count` (tested below), so compare only id/name
    assert [{"id": item["id"], "name": item["name"]} for item in body["items"]] == [
        {"id": first.id, "name": "Drama"},
        {"id": second.id, "name": "Action"},
    ]
    assert body["total"] == 2
    assert body["page"] == 1
    assert body["page_size"] == 20


async def test_list_pagination(
    client: AsyncClient, db_session: AsyncSession, entity: CatalogEntity
) -> None:
    instances = [
        await create_entity(db_session, entity.model, f"Name {i}") for i in range(3)
    ]

    response = await client.get(entity.url, params={"page": 2, "page_size": 2})

    body = response.json()
    assert [item["id"] for item in body["items"]] == [instances[2].id]
    assert body["total"] == 3
    assert body["page"] == 2
    assert body["page_size"] == 2


async def test_list_page_past_end_is_empty(
    client: AsyncClient, db_session: AsyncSession, entity: CatalogEntity
) -> None:
    await create_entity(db_session, entity.model, "Drama")

    response = await client.get(entity.url, params={"page": 5})

    assert response.status_code == 200
    assert response.json()["items"] == []
    assert response.json()["total"] == 1


@pytest.mark.parametrize(
    "params",
    [{"page": 0}, {"page_size": 0}, {"page_size": 101}],
    ids=["page_zero", "page_size_zero", "page_size_too_big"],
)
async def test_list_invalid_pagination_returns_422(
    client: AsyncClient, entity: CatalogEntity, params: dict[str, int]
) -> None:
    response = await client.get(entity.url, params=params)

    assert response.status_code == 422


# --- genres: movie count ---


async def test_list_genres_counts_movies(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    drama = await create_entity(db_session, Genre, "Drama")
    comedy = await create_entity(db_session, Genre, "Comedy")
    empty = await create_entity(db_session, Genre, "Western")
    certification = await create_entity(db_session, Certification, "PG-13")
    await create_movie(
        db_session, name="Movie 1", certification=certification, genres=[drama, comedy]
    )
    await create_movie(
        db_session, name="Movie 2", certification=certification, genres=[drama]
    )

    response = await client.get(GENRES.url)

    assert response.status_code == 200
    assert response.json()["items"] == [
        {"id": drama.id, "name": "Drama", "movies_count": 2},
        {"id": comedy.id, "name": "Comedy", "movies_count": 1},
        {"id": empty.id, "name": "Western", "movies_count": 0},
    ]
    assert response.json()["total"] == 3


async def test_list_genres_total_and_pagination_ignore_movie_links(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """The JOIN with movies must not multiply genres in `items` or `total`."""
    drama = await create_entity(db_session, Genre, "Drama")
    comedy = await create_entity(db_session, Genre, "Comedy")
    certification = await create_entity(db_session, Certification, "PG-13")
    for i in range(3):
        await create_movie(
            db_session, name=f"Movie {i}", certification=certification, genres=[drama]
        )

    response = await client.get(GENRES.url, params={"page": 1, "page_size": 1})

    body = response.json()
    assert body["items"] == [{"id": drama.id, "name": "Drama", "movies_count": 3}]
    assert body["total"] == 2

    second = await client.get(GENRES.url, params={"page": 2, "page_size": 1})
    assert second.json()["items"] == [
        {"id": comedy.id, "name": "Comedy", "movies_count": 0}
    ]


async def test_genre_detail_has_no_movie_count(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    genre = await create_entity(db_session, Genre, "Drama")

    response = await client.get(f"{GENRES.url}/{genre.id}")

    assert response.json() == {"id": genre.id, "name": "Drama"}


# --- detail ---


async def test_get(
    client: AsyncClient, db_session: AsyncSession, entity: CatalogEntity
) -> None:
    instance = await create_entity(db_session, entity.model, "Drama")

    response = await client.get(f"{entity.url}/{instance.id}")

    assert response.status_code == 200
    assert response.json() == {"id": instance.id, "name": "Drama"}


async def test_get_unknown_returns_404(
    client: AsyncClient, entity: CatalogEntity
) -> None:
    response = await client.get(f"{entity.url}/999999")

    assert response.status_code == 404
    assert response.json() == entity.not_found


# --- update ---


async def test_update(
    client: AsyncClient,
    create_user: CreateUser,
    db_session: AsyncSession,
    entity: CatalogEntity,
) -> None:
    instance = await create_entity(db_session, entity.model, "Drama")
    caller = await create_caller(create_user)

    response = await client.patch(
        f"{entity.url}/{instance.id}",
        json={"name": "Thriller"},
        headers=auth_header(caller),
    )

    assert response.status_code == 200
    assert response.json() == {"id": instance.id, "name": "Thriller"}
    await db_session.refresh(instance)
    assert instance.name == "Thriller"


async def test_update_to_its_own_name(
    client: AsyncClient,
    create_user: CreateUser,
    db_session: AsyncSession,
    entity: CatalogEntity,
) -> None:
    instance = await create_entity(db_session, entity.model, "Drama")
    caller = await create_caller(create_user)

    response = await client.patch(
        f"{entity.url}/{instance.id}",
        json={"name": "Drama"},
        headers=auth_header(caller),
    )

    assert response.status_code == 200


async def test_update_to_taken_name_returns_409(
    client: AsyncClient,
    create_user: CreateUser,
    db_session: AsyncSession,
    entity: CatalogEntity,
) -> None:
    await create_entity(db_session, entity.model, "Drama")
    instance = await create_entity(db_session, entity.model, "Comedy")
    caller = await create_caller(create_user)

    response = await client.patch(
        f"{entity.url}/{instance.id}",
        json={"name": "Drama"},
        headers=auth_header(caller),
    )

    assert response.status_code == 409
    assert response.json() == entity.already_exists


async def test_update_unknown_returns_404(
    client: AsyncClient, create_user: CreateUser, entity: CatalogEntity
) -> None:
    caller = await create_caller(create_user)

    response = await client.patch(
        f"{entity.url}/999999", json={"name": "Drama"}, headers=auth_header(caller)
    )

    assert response.status_code == 404
    assert response.json() == entity.not_found


async def test_update_invalid_name_returns_422(
    client: AsyncClient,
    create_user: CreateUser,
    db_session: AsyncSession,
    entity: CatalogEntity,
) -> None:
    instance = await create_entity(db_session, entity.model, "Drama")
    caller = await create_caller(create_user)

    response = await client.patch(
        f"{entity.url}/{instance.id}", json={"name": ""}, headers=auth_header(caller)
    )

    assert response.status_code == 422


# --- delete ---


async def test_delete(
    client: AsyncClient,
    create_user: CreateUser,
    db_session: AsyncSession,
    entity: CatalogEntity,
) -> None:
    instance = await create_entity(db_session, entity.model, "Drama")
    caller = await create_caller(create_user)

    response = await client.delete(
        f"{entity.url}/{instance.id}", headers=auth_header(caller)
    )

    assert response.status_code == 204
    assert response.content == b""
    assert (await client.get(f"{entity.url}/{instance.id}")).status_code == 404


async def test_delete_unknown_returns_404(
    client: AsyncClient, create_user: CreateUser, entity: CatalogEntity
) -> None:
    caller = await create_caller(create_user)

    response = await client.delete(f"{entity.url}/999999", headers=auth_header(caller))

    assert response.status_code == 404
    assert response.json() == entity.not_found


@pytest.mark.parametrize(
    ("catalog", "relation", "link_table", "link_column"),
    [
        (GENRES, "genres", movie_genres, "genre_id"),
        (STARS, "stars", movie_stars, "star_id"),
        (DIRECTORS, "directors", movie_directors, "director_id"),
    ],
    ids=["genres", "stars", "directors"],
)
async def test_delete_unlinks_movies_and_keeps_them(
    client: AsyncClient,
    create_user: CreateUser,
    db_session: AsyncSession,
    catalog: CatalogEntity,
    relation: str,
    link_table: Table,
    link_column: str,
) -> None:
    instance = await create_entity(db_session, catalog.model, "Drama")
    relations: dict[str, Any] = {relation: [instance]}
    movie = await create_movie(db_session, **relations)
    movie_id, instance_id = movie.id, instance.id
    caller = await create_caller(create_user)

    response = await client.delete(
        f"{catalog.url}/{instance_id}", headers=auth_header(caller)
    )

    assert response.status_code == 204
    assert await db_session.scalar(select(Movie.id).where(Movie.id == movie_id))
    links = await db_session.scalar(
        select(func.count())
        .select_from(link_table)
        .where(link_table.c[link_column] == instance_id)
    )
    assert links == 0


async def test_delete_certification_used_by_movie_returns_409(
    client: AsyncClient, create_user: CreateUser, db_session: AsyncSession
) -> None:
    certification = await create_entity(db_session, Certification, "R")
    movie = await create_movie(db_session, certification=certification)
    movie_id, certification_id = movie.id, certification.id
    caller = await create_caller(create_user)

    response = await client.delete(
        f"{CERTIFICATIONS.url}/{certification_id}", headers=auth_header(caller)
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "Certification is in use."}
    stored_certification_id = await db_session.scalar(
        select(Movie.certification_id).where(Movie.id == movie_id)
    )
    assert stored_certification_id == certification_id
