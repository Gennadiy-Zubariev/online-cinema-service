"""Movie CRUD (moderator): create, update, delete, poster upload.

Catalog entities are referenced by id; the response nests them as {id, name}.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock
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
    movie_directors,
    movie_genres,
    movie_stars,
)
from src.movies.service import MAX_POSTER_SIZE
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
    assert body["poster_url"] is None

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


# --- update ---


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


async def stored_genre_ids(db_session: AsyncSession, movie_id: int) -> set[int]:
    result = await db_session.scalars(
        select(movie_genres.c.genre_id).where(movie_genres.c.movie_id == movie_id)
    )
    return set(result.all())


async def test_update_requires_token(client: AsyncClient, movie: Movie) -> None:
    response = await client.patch(movie_url(movie.id), json={"name": "Tenet"})

    assert response.status_code == 401


async def test_update_rejects_regular_user(
    client: AsyncClient, create_user: CreateUser, movie: Movie
) -> None:
    caller = await create_caller(create_user, group=UserGroupEnum.USER)

    response = await client.patch(
        movie_url(movie.id), json={"name": "Tenet"}, headers=auth_header(caller)
    )

    assert response.status_code == 403
    assert response.json() == PERMISSION_DENIED


async def test_update_changes_only_sent_fields(
    client: AsyncClient,
    create_user: CreateUser,
    db_session: AsyncSession,
    catalog: Catalog,
    movie: Movie,
) -> None:
    caller = await create_caller(create_user)

    response = await client.patch(
        movie_url(movie.id),
        json={"name": "  Inception 2  ", "price": "12.50"},
        headers=auth_header(caller),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Inception 2"
    assert body["price"] == "12.50"
    assert body["year"] == 2010
    assert body["meta_score"] == 74
    assert body["certification"] == {"id": catalog.certification.id, "name": "PG-13"}
    assert body["genres"] == [{"id": catalog.genres[0].id, "name": "Drama"}]
    assert body["directors"] == [
        {"id": catalog.director.id, "name": "Christopher Nolan"}
    ]
    assert body["stars"] == [{"id": catalog.star.id, "name": "Cillian Murphy"}]

    await db_session.refresh(movie)
    assert movie.name == "Inception 2"
    assert movie.price == Decimal("12.50")


async def test_update_with_empty_body_changes_nothing(
    client: AsyncClient, create_user: CreateUser, movie: Movie
) -> None:
    caller = await create_caller(create_user)

    response = await client.patch(
        movie_url(movie.id), json={}, headers=auth_header(caller)
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Inception"
    assert response.json()["price"] == "7.99"


async def test_update_returns_presigned_poster_url(
    client: AsyncClient,
    create_user: CreateUser,
    db_session: AsyncSession,
    movie: Movie,
) -> None:
    movie.poster = "posters/1/poster.jpg"
    await db_session.commit()
    caller = await create_caller(create_user)

    response = await client.patch(
        movie_url(movie.id), json={}, headers=auth_header(caller)
    )

    poster_url = response.json()["poster_url"]
    assert poster_url.startswith(get_settings().S3_PUBLIC_ENDPOINT_URL)
    assert "/posters/1/poster.jpg?" in poster_url
    assert "X-Amz-Signature=" in poster_url


async def test_update_clears_nullable_fields(
    client: AsyncClient,
    create_user: CreateUser,
    db_session: AsyncSession,
    movie: Movie,
) -> None:
    caller = await create_caller(create_user)

    response = await client.patch(
        movie_url(movie.id),
        json={"meta_score": None, "gross": None},
        headers=auth_header(caller),
    )

    assert response.status_code == 200
    assert response.json()["meta_score"] is None
    assert response.json()["gross"] is None
    await db_session.refresh(movie)
    assert movie.meta_score is None
    assert movie.gross is None


async def test_update_replaces_genres(
    client: AsyncClient,
    create_user: CreateUser,
    db_session: AsyncSession,
    catalog: Catalog,
    movie: Movie,
) -> None:
    caller = await create_caller(create_user)
    comedy = catalog.genres[1]

    response = await client.patch(
        movie_url(movie.id),
        json={"genre_ids": [comedy.id]},
        headers=auth_header(caller),
    )

    assert response.status_code == 200
    assert response.json()["genres"] == [{"id": comedy.id, "name": "Comedy"}]
    assert await stored_genre_ids(db_session, movie.id) == {comedy.id}


async def test_update_with_empty_lists_unlinks_all(
    client: AsyncClient,
    create_user: CreateUser,
    db_session: AsyncSession,
    movie: Movie,
) -> None:
    caller = await create_caller(create_user)

    response = await client.patch(
        movie_url(movie.id),
        json={"genre_ids": [], "director_ids": [], "star_ids": []},
        headers=auth_header(caller),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["genres"] == []
    assert body["directors"] == []
    assert body["stars"] == []
    assert await stored_genre_ids(db_session, movie.id) == set()


async def test_update_changes_certification(
    client: AsyncClient,
    create_user: CreateUser,
    db_session: AsyncSession,
    movie: Movie,
) -> None:
    other = Certification(name="R")
    db_session.add(other)
    await db_session.commit()
    caller = await create_caller(create_user)

    response = await client.patch(
        movie_url(movie.id),
        json={"certification_id": other.id},
        headers=auth_header(caller),
    )

    assert response.status_code == 200
    assert response.json()["certification"] == {"id": other.id, "name": "R"}
    await db_session.refresh(movie)
    assert movie.certification_id == other.id


async def test_update_unknown_movie_returns_404(
    client: AsyncClient, create_user: CreateUser
) -> None:
    caller = await create_caller(create_user)

    response = await client.patch(
        movie_url(UNKNOWN_ID), json={"name": "Tenet"}, headers=auth_header(caller)
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Movie not found."}


@pytest.mark.parametrize(
    ("body", "entity"),
    [
        ({"certification_id": UNKNOWN_ID}, "Certification"),
        ({"genre_ids": [UNKNOWN_ID]}, "Genre"),
        ({"director_ids": [UNKNOWN_ID]}, "Director"),
        ({"star_ids": [UNKNOWN_ID]}, "Star"),
    ],
    ids=["certification", "genre", "director", "star"],
)
async def test_update_with_unknown_entity_returns_404(
    client: AsyncClient,
    create_user: CreateUser,
    movie: Movie,
    body: dict[str, Any],
    entity: str,
) -> None:
    caller = await create_caller(create_user)

    response = await client.patch(
        movie_url(movie.id), json=body, headers=auth_header(caller)
    )

    assert response.status_code == 404
    assert response.json() == {"detail": f"{entity} not found."}


@pytest.mark.parametrize(
    "extra",
    [{}, {"genre_ids": []}],
    ids=["name_only", "name_and_genres"],
)
async def test_update_to_existing_movie_returns_409(
    client: AsyncClient,
    create_user: CreateUser,
    db_session: AsyncSession,
    catalog: Catalog,
    movie: Movie,
    extra: dict[str, Any],
) -> None:
    """`name_and_genres`: the genre lookup must not autoflush the new name (-> 500)."""
    other = Movie(
        name="Tenet",
        year=movie.year,
        time=movie.time,
        imdb=7.3,
        votes=600000,
        description="Time inversion.",
        price=Decimal("8.99"),
        certification=catalog.certification,
    )
    db_session.add(other)
    await db_session.commit()
    caller = await create_caller(create_user)

    response = await client.patch(
        movie_url(movie.id),
        json={"name": "Tenet", **extra},
        headers=auth_header(caller),
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "Movie already exists."}


@pytest.mark.parametrize(
    "body",
    [
        {"name": None},
        {"price": None},
        {"certification_id": None},
        {"genre_ids": None},
        {"name": ""},
        {"imdb": 10.1},
        {"price": "9.999"},
    ],
    ids=[
        "null_name",
        "null_price",
        "null_certification",
        "null_genre_ids",
        "empty_name",
        "imdb_above_10",
        "price_three_decimals",
    ],
)
async def test_update_invalid_body_returns_422(
    client: AsyncClient,
    create_user: CreateUser,
    movie: Movie,
    body: dict[str, Any],
) -> None:
    caller = await create_caller(create_user)

    response = await client.patch(
        movie_url(movie.id), json=body, headers=auth_header(caller)
    )

    assert response.status_code == 422


# --- delete ---


async def count_rows(db_session: AsyncSession, table: Any) -> int:
    return await db_session.scalar(select(func.count()).select_from(table)) or 0


async def test_delete_requires_token(client: AsyncClient, movie: Movie) -> None:
    response = await client.delete(movie_url(movie.id))

    assert response.status_code == 401


async def test_delete_rejects_regular_user(
    client: AsyncClient, create_user: CreateUser, movie: Movie
) -> None:
    caller = await create_caller(create_user, group=UserGroupEnum.USER)

    response = await client.delete(movie_url(movie.id), headers=auth_header(caller))

    assert response.status_code == 403
    assert response.json() == PERMISSION_DENIED


async def test_delete(
    client: AsyncClient,
    create_user: CreateUser,
    db_session: AsyncSession,
    movie: Movie,
) -> None:
    caller = await create_caller(create_user)

    response = await client.delete(movie_url(movie.id), headers=auth_header(caller))

    assert response.status_code == 204
    assert response.content == b""
    assert await count_rows(db_session, Movie) == 0


async def test_delete_unlinks_but_keeps_catalog_entities(
    client: AsyncClient,
    create_user: CreateUser,
    db_session: AsyncSession,
    movie: Movie,
) -> None:
    caller = await create_caller(create_user)

    await client.delete(movie_url(movie.id), headers=auth_header(caller))

    assert await count_rows(db_session, movie_genres) == 0
    assert await count_rows(db_session, movie_directors) == 0
    assert await count_rows(db_session, movie_stars) == 0
    assert await count_rows(db_session, Certification) == 1
    assert await count_rows(db_session, Genre) == 2
    assert await count_rows(db_session, Director) == 1
    assert await count_rows(db_session, Star) == 1


async def test_delete_unknown_movie_returns_404(
    client: AsyncClient, create_user: CreateUser
) -> None:
    caller = await create_caller(create_user)

    response = await client.delete(movie_url(UNKNOWN_ID), headers=auth_header(caller))

    assert response.status_code == 404
    assert response.json() == {"detail": "Movie not found."}


# --- poster ---


@pytest.fixture
def storage_mock(monkeypatch: pytest.MonkeyPatch) -> dict[str, MagicMock]:
    """Replace S3 calls where the service uses them, so tests need no MinIO."""
    mocks = {"upload_file": MagicMock(), "delete_file": MagicMock()}
    for name, mock in mocks.items():
        monkeypatch.setattr(f"src.movies.service.{name}", mock)
    return mocks


def poster_url(movie_id: int) -> str:
    return f"{movie_url(movie_id)}/poster"


async def test_upload_poster_requires_token(
    client: AsyncClient, movie: Movie, storage_mock: dict[str, MagicMock]
) -> None:
    response = await client.put(
        poster_url(movie.id), files={"file": ("p.png", b"img", "image/png")}
    )

    assert response.status_code == 401
    storage_mock["upload_file"].assert_not_called()


async def test_upload_poster_rejects_regular_user(
    client: AsyncClient,
    create_user: CreateUser,
    movie: Movie,
    storage_mock: dict[str, MagicMock],
) -> None:
    caller = await create_caller(create_user, group=UserGroupEnum.USER)

    response = await client.put(
        poster_url(movie.id),
        files={"file": ("p.png", b"img", "image/png")},
        headers=auth_header(caller),
    )

    assert response.status_code == 403
    assert response.json() == PERMISSION_DENIED
    storage_mock["upload_file"].assert_not_called()


async def test_upload_poster_stores_key_and_returns_movie(
    client: AsyncClient,
    create_user: CreateUser,
    db_session: AsyncSession,
    catalog: Catalog,
    movie: Movie,
    storage_mock: dict[str, MagicMock],
) -> None:
    caller = await create_caller(create_user)

    response = await client.put(
        poster_url(movie.id),
        files={"file": ("my poster.JPG", b"jpeg-bytes", "image/jpeg")},
        headers=auth_header(caller),
    )

    assert response.status_code == 200
    storage_mock["upload_file"].assert_called_once()
    key, data, content_type = storage_mock["upload_file"].call_args.args
    # The key is generated by the server, the original file name is ignored.
    assert key.startswith(f"posters/{movie.id}/")
    assert key.endswith(".jpg")
    assert "poster.JPG" not in key
    assert (data, content_type) == (b"jpeg-bytes", "image/jpeg")
    storage_mock["delete_file"].assert_not_called()

    await db_session.refresh(movie)
    assert movie.poster == key

    body = response.json()
    assert body["poster_url"].startswith(get_settings().S3_PUBLIC_ENDPOINT_URL)
    assert key in body["poster_url"]
    # Full movie is returned, relations included.
    assert body["name"] == "Inception"
    assert body["certification"] == {"id": catalog.certification.id, "name": "PG-13"}
    assert body["genres"] == [{"id": catalog.genres[0].id, "name": "Drama"}]


async def test_upload_poster_replaces_and_deletes_old_file(
    client: AsyncClient,
    create_user: CreateUser,
    movie: Movie,
    storage_mock: dict[str, MagicMock],
) -> None:
    headers = auth_header(await create_caller(create_user))
    await client.put(
        poster_url(movie.id),
        files={"file": ("a.png", b"old", "image/png")},
        headers=headers,
    )
    old_key = storage_mock["upload_file"].call_args.args[0]

    response = await client.put(
        poster_url(movie.id),
        files={"file": ("b.webp", b"new", "image/webp")},
        headers=headers,
    )

    assert response.status_code == 200
    new_key = storage_mock["upload_file"].call_args.args[0]
    assert new_key != old_key
    assert new_key.endswith(".webp")
    storage_mock["delete_file"].assert_called_once_with(old_key)


async def test_update_keeps_poster(
    client: AsyncClient,
    create_user: CreateUser,
    movie: Movie,
    storage_mock: dict[str, MagicMock],
) -> None:
    headers = auth_header(await create_caller(create_user))
    await client.put(
        poster_url(movie.id),
        files={"file": ("p.png", b"img", "image/png")},
        headers=headers,
    )

    response = await client.patch(
        movie_url(movie.id), json={"name": "Inception 2"}, headers=headers
    )

    assert response.json()["poster_url"] is not None


async def test_upload_poster_unknown_movie_returns_404(
    client: AsyncClient,
    create_user: CreateUser,
    storage_mock: dict[str, MagicMock],
) -> None:
    caller = await create_caller(create_user)

    response = await client.put(
        poster_url(UNKNOWN_ID),
        files={"file": ("p.png", b"img", "image/png")},
        headers=auth_header(caller),
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Movie not found."}
    storage_mock["upload_file"].assert_not_called()


@pytest.mark.parametrize("content_type", ["image/gif", "image/svg+xml", "text/plain"])
async def test_upload_poster_rejects_unsupported_type(
    client: AsyncClient,
    create_user: CreateUser,
    db_session: AsyncSession,
    movie: Movie,
    storage_mock: dict[str, MagicMock],
    content_type: str,
) -> None:
    caller = await create_caller(create_user)

    response = await client.put(
        poster_url(movie.id),
        files={"file": ("file", b"data", content_type)},
        headers=auth_header(caller),
    )

    assert response.status_code == 415
    assert response.json() == {"detail": "Image must be a JPEG, PNG or WebP image."}
    storage_mock["upload_file"].assert_not_called()
    await db_session.refresh(movie)
    assert movie.poster is None


async def test_upload_poster_rejects_too_large_file(
    client: AsyncClient,
    create_user: CreateUser,
    movie: Movie,
    storage_mock: dict[str, MagicMock],
) -> None:
    caller = await create_caller(create_user)

    response = await client.put(
        poster_url(movie.id),
        files={"file": ("big.png", b"x" * (MAX_POSTER_SIZE + 1), "image/png")},
        headers=auth_header(caller),
    )

    assert response.status_code == 413
    assert response.json() == {"detail": "Image must not exceed 5 MB."}
    storage_mock["upload_file"].assert_not_called()


async def test_upload_poster_accepts_file_of_max_size(
    client: AsyncClient,
    create_user: CreateUser,
    movie: Movie,
    storage_mock: dict[str, MagicMock],
) -> None:
    caller = await create_caller(create_user)

    response = await client.put(
        poster_url(movie.id),
        files={"file": ("max.png", b"x" * MAX_POSTER_SIZE, "image/png")},
        headers=auth_header(caller),
    )

    assert response.status_code == 200
    storage_mock["upload_file"].assert_called_once()


async def test_upload_poster_without_file_returns_422(
    client: AsyncClient,
    create_user: CreateUser,
    movie: Movie,
    storage_mock: dict[str, MagicMock],
) -> None:
    caller = await create_caller(create_user)

    response = await client.put(poster_url(movie.id), headers=auth_header(caller))

    assert response.status_code == 422
    storage_mock["upload_file"].assert_not_called()
