"""Movie CRUD (moderator): create, update, delete, poster upload;
catalog (public): movie detail, movie list with filters, sorting and search.

Catalog entities are referenced by id; the response nests them as {id, name}.
"""

from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.accounts.models import UserGroupEnum
from src.cart.models import Cart, CartItem
from src.config.settings import get_settings
from src.movies.models import (
    Certification,
    Director,
    Genre,
    Movie,
    MovieRating,
    MovieReaction,
    Star,
    movie_directors,
    movie_genres,
    movie_stars,
)
from src.movies.movies_service import MAX_POSTER_SIZE
from src.orders.models import Order, OrderItem, OrderStatusEnum
from tests.integration.conftest import (
    UNKNOWN_ID,
    Catalog,
    CreateUser,
    auth_header,
    create_caller,
)
from tests.integration.movies.conftest import MOVIES_URL, PERMISSION_DENIED, movie_url


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
    storage_mock: dict[str, MagicMock],
) -> None:
    caller = await create_caller(create_user)

    response = await client.delete(movie_url(movie.id), headers=auth_header(caller))

    assert response.status_code == 204
    assert response.content == b""
    assert await count_rows(db_session, Movie) == 0
    # No poster -> nothing to delete in S3.
    storage_mock["delete_file"].assert_not_called()


async def test_delete_removes_poster_file(
    client: AsyncClient,
    create_user: CreateUser,
    db_session: AsyncSession,
    movie: Movie,
    storage_mock: dict[str, MagicMock],
) -> None:
    movie.poster = "posters/1/poster.jpg"
    await db_session.commit()
    caller = await create_caller(create_user)

    response = await client.delete(movie_url(movie.id), headers=auth_header(caller))

    assert response.status_code == 204
    assert await count_rows(db_session, Movie) == 0
    storage_mock["delete_file"].assert_called_once_with("posters/1/poster.jpg")


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
    client: AsyncClient,
    create_user: CreateUser,
    storage_mock: dict[str, MagicMock],
) -> None:
    caller = await create_caller(create_user)

    response = await client.delete(movie_url(UNKNOWN_ID), headers=auth_header(caller))

    assert response.status_code == 404
    assert response.json() == {"detail": "Movie not found."}
    storage_mock["delete_file"].assert_not_called()


@pytest.mark.parametrize(
    "status", [OrderStatusEnum.PENDING, OrderStatusEnum.PAID, OrderStatusEnum.CANCELED]
)
async def test_delete_movie_in_order_returns_409(
    client: AsyncClient,
    create_user: CreateUser,
    db_session: AsyncSession,
    movie: Movie,
    storage_mock: dict[str, MagicMock],
    status: OrderStatusEnum,
) -> None:
    movie.poster = "posters/1/poster.jpg"
    caller = await create_caller(create_user)
    order = Order(user_id=caller.id, status=status)
    db_session.add(order)
    await db_session.flush()
    db_session.add(
        OrderItem(order_id=order.id, movie_id=movie.id, price_at_order=movie.price)
    )
    await db_session.commit()

    response = await client.delete(movie_url(movie.id), headers=auth_header(caller))

    assert response.status_code == 409
    assert response.json() == {"detail": "Movie is in use."}
    assert await count_rows(db_session, Movie) == 1
    storage_mock["delete_file"].assert_not_called()


async def test_delete_movie_in_cart_removes_cart_item(
    client: AsyncClient,
    create_user: CreateUser,
    db_session: AsyncSession,
    movie: Movie,
) -> None:
    caller = await create_caller(create_user)
    cart = Cart(user_id=caller.id)
    db_session.add(cart)
    await db_session.flush()
    db_session.add(CartItem(cart_id=cart.id, movie_id=movie.id))
    await db_session.commit()

    response = await client.delete(movie_url(movie.id), headers=auth_header(caller))

    assert response.status_code == 204
    assert await count_rows(db_session, CartItem) == 0
    assert await count_rows(db_session, Cart) == 1


# --- poster ---


@pytest.fixture
def storage_mock(monkeypatch: pytest.MonkeyPatch) -> dict[str, MagicMock]:
    """Replace S3 calls where the service uses them, so tests need no MinIO."""
    mocks = {"upload_file": MagicMock(), "delete_file": MagicMock()}
    for name, mock in mocks.items():
        monkeypatch.setattr(f"src.movies.movies_service.{name}", mock)
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


# --- detail (public) ---


async def test_get_movie_detail_is_public(
    client: AsyncClient, catalog: Catalog, movie: Movie
) -> None:
    response = await client.get(movie_url(movie.id))

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == movie.id
    assert body["uuid"] == str(movie.uuid)
    assert body["name"] == "Inception"
    assert body["description"] == (
        "A thief who steals corporate secrets through dreams."
    )
    assert body["price"] == "7.99"
    assert body["certification"] == {"id": catalog.certification.id, "name": "PG-13"}
    assert body["genres"] == [{"id": catalog.genres[0].id, "name": "Drama"}]
    assert body["directors"] == [
        {"id": catalog.director.id, "name": "Christopher Nolan"}
    ]
    assert body["stars"] == [{"id": catalog.star.id, "name": "Cillian Murphy"}]
    assert body["poster_url"] is None


async def test_get_movie_detail_with_poster(
    client: AsyncClient, db_session: AsyncSession, movie: Movie
) -> None:
    movie.poster = "posters/1/poster.jpg"
    await db_session.commit()

    response = await client.get(movie_url(movie.id))

    assert "/posters/1/poster.jpg?" in response.json()["poster_url"]


async def test_get_movie_detail_loads_relations_in_fresh_session(
    client: AsyncClient, db_session: AsyncSession, movie: Movie
) -> None:
    """Nothing is in the identity map: relations must be eager-loaded, not lazy."""
    db_session.expunge_all()

    response = await client.get(movie_url(movie.id))

    assert response.status_code == 200
    assert len(response.json()["genres"]) == 1


async def test_get_unknown_movie_returns_404(client: AsyncClient) -> None:
    response = await client.get(movie_url(UNKNOWN_ID))

    assert response.status_code == 404
    assert response.json() == {"detail": "Movie not found."}


async def test_get_movie_with_non_integer_id_returns_422(client: AsyncClient) -> None:
    response = await client.get(f"{MOVIES_URL}/abc")

    assert response.status_code == 422


# --- detail: likes, dislikes, rating ---


async def create_voter_ids(create_user: CreateUser, count: int) -> list[int]:
    """Save `count` active users (voter0@..., voter1@...) and return their ids."""
    users = [
        await create_user(
            email=f"voter{i}@example.com", is_active=True, token_expires_in=None
        )
        for i in range(count)
    ]
    return [user.id for user in users]


async def test_get_movie_detail_without_reactions_and_ratings(
    client: AsyncClient, movie: Movie
) -> None:
    response = await client.get(movie_url(movie.id))

    body = response.json()
    assert body["likes"] == 0
    assert body["dislikes"] == 0
    assert body["rating"] is None
    assert body["ratings_count"] == 0


async def test_get_movie_detail_counts_likes_and_dislikes(
    client: AsyncClient,
    db_session: AsyncSession,
    create_user: CreateUser,
    movie: Movie,
) -> None:
    user_ids = await create_voter_ids(create_user, 3)
    db_session.add_all(
        MovieReaction(user_id=user_id, movie_id=movie.id, is_like=is_like)
        for user_id, is_like in zip(user_ids, [True, True, False])
    )
    await db_session.commit()

    response = await client.get(movie_url(movie.id))

    body = response.json()
    assert body["likes"] == 2
    assert body["dislikes"] == 1


@pytest.mark.parametrize(
    ("scores", "expected_rating"),
    [([10], 10.0), ([1, 2], 1.5), ([7, 8, 8], 7.7)],
    ids=["single", "half", "rounded"],
)
async def test_get_movie_detail_averages_ratings(
    client: AsyncClient,
    db_session: AsyncSession,
    create_user: CreateUser,
    movie: Movie,
    scores: list[int],
    expected_rating: float,
) -> None:
    user_ids = await create_voter_ids(create_user, len(scores))
    db_session.add_all(
        MovieRating(user_id=user_id, movie_id=movie.id, score=score)
        for user_id, score in zip(user_ids, scores)
    )
    await db_session.commit()

    response = await client.get(movie_url(movie.id))

    body = response.json()
    assert body["rating"] == expected_rating
    assert body["ratings_count"] == len(scores)


async def test_get_movie_detail_ignores_stats_of_other_movies(
    client: AsyncClient,
    db_session: AsyncSession,
    create_user: CreateUser,
    catalog: Catalog,
    movie: Movie,
) -> None:
    [other_movie] = await create_movies(db_session, catalog, 1)
    [user_id] = await create_voter_ids(create_user, 1)
    db_session.add_all(
        [
            MovieReaction(user_id=user_id, movie_id=other_movie.id, is_like=True),
            MovieRating(user_id=user_id, movie_id=other_movie.id, score=9),
        ]
    )
    await db_session.commit()

    response = await client.get(movie_url(movie.id))

    body = response.json()
    assert body["likes"] == 0
    assert body["rating"] is None
    assert body["ratings_count"] == 0


# --- list (public) ---


async def create_movies(
    db_session: AsyncSession, catalog: Catalog, count: int
) -> list[Movie]:
    """Save `count` movies (Movie 0, Movie 1, ...) linked to the first genre."""
    movies = [
        Movie(
            name=f"Movie {i}",
            year=2000 + i,
            time=100,
            imdb=7.0,
            votes=1000,
            description="Description.",
            price=Decimal("5.00"),
            certification=catalog.certification,
            genres=[catalog.genres[0]],
        )
        for i in range(count)
    ]
    db_session.add_all(movies)
    await db_session.commit()
    return movies


async def test_list_empty_catalog(client: AsyncClient, create_schema: None) -> None:
    response = await client.get(MOVIES_URL)

    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0, "page": 1, "page_size": 20}


async def test_list_is_public_and_returns_short_items(
    client: AsyncClient, catalog: Catalog, movie: Movie
) -> None:
    response = await client.get(MOVIES_URL)

    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {
                "id": movie.id,
                "uuid": str(movie.uuid),
                "name": "Inception",
                "year": 2010,
                "time": 148,
                "imdb": 8.8,
                "votes": 2500000,
                "price": "7.99",
                "genres": [{"id": catalog.genres[0].id, "name": "Drama"}],
                "poster_url": None,
            }
        ],
        "total": 1,
        "page": 1,
        "page_size": 20,
    }


async def test_list_item_with_poster(
    client: AsyncClient, db_session: AsyncSession, movie: Movie
) -> None:
    movie.poster = "posters/1/poster.jpg"
    await db_session.commit()

    response = await client.get(MOVIES_URL)

    assert "/posters/1/poster.jpg?" in response.json()["items"][0]["poster_url"]


async def test_list_ordered_by_id_and_paginated(
    client: AsyncClient, db_session: AsyncSession, catalog: Catalog
) -> None:
    movies = await create_movies(db_session, catalog, 5)

    first_page = await client.get(MOVIES_URL, params={"page": 1, "page_size": 2})
    last_page = await client.get(MOVIES_URL, params={"page": 3, "page_size": 2})

    assert [item["id"] for item in first_page.json()["items"]] == [
        movies[0].id,
        movies[1].id,
    ]
    assert [item["id"] for item in last_page.json()["items"]] == [movies[4].id]
    assert last_page.json()["total"] == 5
    assert last_page.json()["page"] == 3
    assert last_page.json()["page_size"] == 2


async def test_list_page_past_end_is_empty(
    client: AsyncClient, db_session: AsyncSession, catalog: Catalog
) -> None:
    await create_movies(db_session, catalog, 2)

    response = await client.get(MOVIES_URL, params={"page": 5})

    assert response.status_code == 200
    assert response.json()["items"] == []
    assert response.json()["total"] == 2


async def test_list_loads_genres_in_fresh_session(
    client: AsyncClient, db_session: AsyncSession, catalog: Catalog
) -> None:
    """Nothing is in the identity map: genres must be eager-loaded, not lazy."""
    await create_movies(db_session, catalog, 3)
    db_session.expunge_all()

    response = await client.get(MOVIES_URL)

    assert response.status_code == 200
    assert all(len(item["genres"]) == 1 for item in response.json()["items"])


@pytest.mark.parametrize(
    "params",
    [{"page": 0}, {"page_size": 0}, {"page_size": 101}],
    ids=["page_zero", "page_size_zero", "page_size_too_big"],
)
async def test_list_invalid_pagination_returns_422(
    client: AsyncClient, params: dict[str, int]
) -> None:
    response = await client.get(MOVIES_URL, params=params)

    assert response.status_code == 422


# --- list: filters ---


@pytest.fixture
async def filter_movies(db_session: AsyncSession, catalog: Catalog) -> None:
    """Old (2000, 6.0), Middle (2005, 7.5), New (2010, 8.5)."""
    db_session.add_all(
        [
            Movie(
                name=name,
                year=year,
                time=100,
                imdb=imdb,
                votes=1000,
                description="Description.",
                price=Decimal("5.00"),
                certification=catalog.certification,
            )
            for name, year, imdb in [
                ("Old", 2000, 6.0),
                ("Middle", 2005, 7.5),
                ("New", 2010, 8.5),
            ]
        ]
    )
    await db_session.commit()


def names(response_json: dict[str, Any]) -> list[str]:
    return [item["name"] for item in response_json["items"]]


@pytest.mark.parametrize(
    ("params", "expected"),
    [
        ({}, ["Old", "Middle", "New"]),
        ({"year_from": 2005}, ["Middle", "New"]),
        ({"year_to": 2005}, ["Old", "Middle"]),
        ({"year_from": 2005, "year_to": 2005}, ["Middle"]),
        ({"imdb_min": 7.5}, ["Middle", "New"]),
        ({"imdb_max": 7.5}, ["Old", "Middle"]),
        ({"imdb_min": 7, "imdb_max": 8}, ["Middle"]),
        ({"year_from": 2001, "imdb_min": 8}, ["New"]),
        ({"year_from": 2010, "year_to": 2000}, []),
    ],
    ids=[
        "no_filters",
        "year_from_inclusive",
        "year_to_inclusive",
        "exact_year",
        "imdb_min_inclusive",
        "imdb_max_inclusive",
        "imdb_range",
        "year_and_imdb",
        "inverted_range_is_empty",
    ],
)
async def test_list_filters(
    client: AsyncClient,
    filter_movies: None,
    params: dict[str, float],
    expected: list[str],
) -> None:
    response = await client.get(MOVIES_URL, params=params)

    assert response.status_code == 200
    assert names(response.json()) == expected
    assert response.json()["total"] == len(expected)


async def test_list_total_counts_filtered_movies_not_page(
    client: AsyncClient, filter_movies: None
) -> None:
    response = await client.get(MOVIES_URL, params={"year_from": 2005, "page_size": 1})

    assert names(response.json()) == ["Middle"]
    assert response.json()["total"] == 2


@pytest.fixture
async def genre_movies(db_session: AsyncSession, catalog: Catalog) -> None:
    """Drama: Heat, Up (Up is also a Comedy); Comedy: Up, Big; no genre: Plain."""
    drama, comedy = catalog.genres
    db_session.add_all(
        Movie(
            name=name,
            year=year,
            time=100,
            imdb=7.0,
            votes=votes,
            description="Description.",
            price=Decimal("5.00"),
            certification=catalog.certification,
            genres=genres,
        )
        for name, year, votes, genres in [
            ("Heat", 1995, 700, [drama]),
            ("Up", 2009, 900, [drama, comedy]),
            ("Big", 1988, 300, [comedy]),
            ("Plain", 2000, 100, []),
        ]
    )
    await db_session.commit()


@pytest.mark.parametrize(
    ("genre", "params", "expected"),
    [
        (0, {}, ["Heat", "Up"]),
        (1, {}, ["Up", "Big"]),
        (0, {"sort_by": "votes", "order": "desc"}, ["Up", "Heat"]),
        (1, {"year_from": 2000}, ["Up"]),
    ],
    ids=["drama", "comedy", "with_sorting", "with_year_filter"],
)
async def test_list_filters_by_genre(
    client: AsyncClient,
    catalog: Catalog,
    genre_movies: None,
    genre: int,
    params: dict[str, Any],
    expected: list[str],
) -> None:
    """A movie with several genres (Up) is listed once and counted once."""
    genre_id = catalog.genres[genre].id

    response = await client.get(MOVIES_URL, params={"genre_id": genre_id, **params})

    assert response.status_code == 200
    assert names(response.json()) == expected
    assert response.json()["total"] == len(expected)


async def test_list_filter_by_unknown_genre_is_empty(
    client: AsyncClient, genre_movies: None
) -> None:
    response = await client.get(MOVIES_URL, params={"genre_id": UNKNOWN_ID})

    assert response.status_code == 200
    assert response.json()["items"] == []
    assert response.json()["total"] == 0


@pytest.mark.parametrize(
    "params",
    [
        {"year_from": 1887},
        {"year_to": "abc"},
        {"imdb_min": 10.1},
        {"imdb_max": -0.1},
        {"genre_id": "abc"},
    ],
    ids=[
        "year_too_early",
        "year_not_int",
        "imdb_above_10",
        "imdb_negative",
        "genre_not_int",
    ],
)
async def test_list_invalid_filter_returns_422(
    client: AsyncClient, params: dict[str, Any]
) -> None:
    response = await client.get(MOVIES_URL, params=params)

    assert response.status_code == 422


# --- list: sorting ---


@pytest.fixture
async def sort_movies(db_session: AsyncSession, catalog: Catalog) -> list[Movie]:
    """A (2010, $9.99, 500 votes), B (2000, $4.99, 900), C (2005, $9.99, 100).

    A and C share a price, so price sorting needs the id tie-breaker.
    """
    movies = [
        Movie(
            name=name,
            year=year,
            time=100,
            imdb=7.0,
            votes=votes,
            description="Description.",
            price=Decimal(price),
            certification=catalog.certification,
        )
        for name, year, price, votes in [
            ("A", 2010, "9.99", 500),
            ("B", 2000, "4.99", 900),
            ("C", 2005, "9.99", 100),
        ]
    ]
    db_session.add_all(movies)
    await db_session.commit()
    return movies


@pytest.mark.parametrize(
    ("params", "expected"),
    [
        ({}, ["A", "B", "C"]),
        ({"sort_by": "id", "order": "desc"}, ["C", "B", "A"]),
        ({"sort_by": "price"}, ["B", "A", "C"]),
        ({"sort_by": "price", "order": "desc"}, ["A", "C", "B"]),
        ({"sort_by": "year"}, ["B", "C", "A"]),
        ({"sort_by": "year", "order": "desc"}, ["A", "C", "B"]),
        ({"sort_by": "votes"}, ["C", "A", "B"]),
        ({"sort_by": "votes", "order": "desc"}, ["B", "A", "C"]),
        ({"order": "desc"}, ["C", "B", "A"]),
    ],
    ids=[
        "default_id_asc",
        "id_desc",
        "price_asc",
        "price_desc_ties_by_id",
        "year_asc",
        "year_desc",
        "votes_asc",
        "votes_desc",
        "order_without_sort_by",
    ],
)
async def test_list_sorting(
    client: AsyncClient,
    sort_movies: list[Movie],
    params: dict[str, str],
    expected: list[str],
) -> None:
    response = await client.get(MOVIES_URL, params=params)

    assert response.status_code == 200
    assert names(response.json()) == expected


async def test_list_sorting_is_stable_across_pages(
    client: AsyncClient, sort_movies: list[Movie]
) -> None:
    """Equal prices (A, C) must not repeat or vanish between pages."""
    pages = [
        await client.get(
            MOVIES_URL, params={"sort_by": "price", "page": page, "page_size": 1}
        )
        for page in (1, 2, 3)
    ]

    assert [names(page.json()) for page in pages] == [["B"], ["A"], ["C"]]


async def test_list_sorting_with_filter(
    client: AsyncClient, sort_movies: list[Movie]
) -> None:
    response = await client.get(
        MOVIES_URL, params={"year_from": 2005, "sort_by": "year", "order": "desc"}
    )

    assert names(response.json()) == ["A", "C"]
    assert response.json()["total"] == 2


@pytest.mark.parametrize(
    "params",
    [{"sort_by": "name"}, {"sort_by": "PRICE"}, {"order": "up"}],
    ids=["unknown_field", "wrong_case", "unknown_order"],
)
async def test_list_invalid_sorting_returns_422(
    client: AsyncClient, params: dict[str, str]
) -> None:
    response = await client.get(MOVIES_URL, params=params)

    assert response.status_code == 422


# --- list: search ---


@pytest.fixture
async def search_movies(db_session: AsyncSession, catalog: Catalog) -> None:
    """Movies whose name, description, stars and directors differ."""

    def movie_with(
        name: str,
        description: str,
        stars: tuple[str, ...] = (),
        directors: tuple[str, ...] = (),
        year: int = 2000,
    ) -> Movie:
        return Movie(
            name=name,
            year=year,
            time=100,
            imdb=7.0,
            votes=1000,
            description=description,
            price=Decimal("5.00"),
            certification=catalog.certification,
            stars=[Star(name=star) for star in stars],
            directors=[Director(name=director) for director in directors],
        )

    db_session.add_all(
        [
            movie_with(
                "The Dark Knight",
                "Batman fights crime in Gotham.",
                stars=("Christian Bale", "Heath Ledger"),
                directors=("Christopher Nolan Jr",),
                year=2008,
            ),
            movie_with(
                "Amelie",
                "A shy waitress in Paris.",
                stars=("Audrey Tautou",),
                directors=("Jean-Pierre Jeunet",),
                year=2001,
            ),
            movie_with("100% Love", "Romance."),
            movie_with("AXB Story", "Plain text."),
        ]
    )
    await db_session.commit()


@pytest.mark.parametrize(
    ("search", "expected"),
    [
        ("dark", ["The Dark Knight"]),
        ("GOTHAM", ["The Dark Knight"]),
        ("tautou", ["Amelie"]),
        ("jeunet", ["Amelie"]),
        ("  amelie  ", ["Amelie"]),
        ("100%", ["100% Love"]),
        ("a_b", []),
        ("nothing like this", []),
    ],
    ids=[
        "name",
        "description_case_insensitive",
        "star",
        "director",
        "strips_whitespace",
        "percent_is_literal",
        "underscore_is_literal",
        "no_match",
    ],
)
async def test_list_search(
    client: AsyncClient, search_movies: None, search: str, expected: list[str]
) -> None:
    response = await client.get(MOVIES_URL, params={"search": search})

    assert response.status_code == 200
    assert names(response.json()) == expected
    assert response.json()["total"] == len(expected)


async def test_list_search_returns_movie_once_for_several_matches(
    client: AsyncClient, search_movies: None
) -> None:
    """ "chris" matches two stars' and the director's names of one movie."""
    response = await client.get(MOVIES_URL, params={"search": "chris"})

    assert names(response.json()) == ["The Dark Knight"]
    assert response.json()["total"] == 1


@pytest.mark.parametrize("search", ["", "   "], ids=["empty", "whitespace"])
async def test_list_empty_search_is_ignored(
    client: AsyncClient, search_movies: None, search: str
) -> None:
    response = await client.get(MOVIES_URL, params={"search": search})

    assert response.status_code == 200
    assert response.json()["total"] == 4


async def test_list_search_with_filter_and_sorting(
    client: AsyncClient, search_movies: None
) -> None:
    response = await client.get(
        MOVIES_URL,
        params={"search": "a", "year_from": 2001, "sort_by": "year", "order": "desc"},
    )

    assert names(response.json()) == ["The Dark Knight", "Amelie"]


async def test_list_search_too_long_returns_422(client: AsyncClient) -> None:
    response = await client.get(MOVIES_URL, params={"search": "a" * 256})

    assert response.status_code == 422
