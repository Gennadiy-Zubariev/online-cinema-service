"""Purchased movies ("My movies") of the current user."""

from decimal import Decimal
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.accounts.models import User, UserGroupEnum
from src.movies.models import FavoriteMovie, Movie, PurchasedMovie
from tests.integration.conftest import Catalog, CreateUser, auth_header, create_caller

PURCHASED_URL = "/api/v1/purchased"


def names(response_json: dict[str, Any]) -> list[str]:
    return [item["name"] for item in response_json["items"]]


@pytest.fixture
async def user(create_user: CreateUser) -> User:
    return await create_caller(create_user, group=UserGroupEnum.USER)


@pytest.fixture
async def other_user(create_user: CreateUser) -> User:
    return await create_user(
        email="other@example.com", is_active=True, token_expires_in=None
    )


@pytest.fixture
async def purchased(
    db_session: AsyncSession, catalog: Catalog, user: User, other_user: User
) -> list[Movie]:
    """Alpha, Beta, Gamma are purchased by `user`; Delta - only by `other_user`."""
    movies = [
        Movie(
            name=name,
            year=year,
            time=100,
            imdb=imdb,
            votes=1000,
            description=description,
            price=Decimal(price),
            certification=catalog.certification,
            genres=[catalog.genres[0]],
        )
        for name, year, imdb, price, description in [
            ("Alpha", 2001, 7.0, "5.00", "A heist."),
            ("Beta", 2005, 8.0, "9.00", "A space heist."),
            ("Gamma", 2010, 9.0, "3.00", "A love story."),
            ("Delta", 2008, 9.5, "4.00", "A heist in Paris."),
        ]
    ]
    db_session.add_all(movies)
    await db_session.commit()
    db_session.add_all(
        [PurchasedMovie(user_id=user.id, movie_id=m.id) for m in movies[:3]]
        + [PurchasedMovie(user_id=other_user.id, movie_id=movies[3].id)]
    )
    await db_session.commit()
    return movies


async def test_list_purchased_requires_token(client: AsyncClient) -> None:
    response = await client.get(PURCHASED_URL)

    assert response.status_code == 401


async def test_list_purchased_empty(
    client: AsyncClient, user: User, movie: Movie
) -> None:
    """A movie in the catalog that the user did not buy is not listed."""
    response = await client.get(PURCHASED_URL, headers=auth_header(user))

    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0, "page": 1, "page_size": 20}


async def test_list_purchased_ignores_favorites(
    client: AsyncClient, db_session: AsyncSession, user: User, movie: Movie
) -> None:
    """Favorites live in another table: a favorite movie is not purchased."""
    db_session.add(FavoriteMovie(user_id=user.id, movie_id=movie.id))
    await db_session.commit()

    response = await client.get(PURCHASED_URL, headers=auth_header(user))

    assert response.json()["total"] == 0


async def test_list_purchased_returns_only_own_movies_as_short_items(
    client: AsyncClient, user: User, catalog: Catalog, purchased: list[Movie]
) -> None:
    response = await client.get(PURCHASED_URL, headers=auth_header(user))

    assert response.status_code == 200
    body = response.json()
    assert names(body) == ["Alpha", "Beta", "Gamma"]
    assert body["total"] == 3
    item = body["items"][0]
    assert item["id"] == purchased[0].id
    assert item["price"] == "5.00"
    assert item["genres"] == [{"id": catalog.genres[0].id, "name": "Drama"}]
    assert item["poster_url"] is None
    assert "description" not in item


async def test_list_purchased_of_other_user(
    client: AsyncClient, other_user: User, purchased: list[Movie]
) -> None:
    response = await client.get(PURCHASED_URL, headers=auth_header(other_user))

    assert names(response.json()) == ["Delta"]


@pytest.mark.parametrize(
    ("params", "expected"),
    [
        ({"year_from": 2005}, ["Beta", "Gamma"]),
        ({"imdb_max": 8.0}, ["Alpha", "Beta"]),
        ({"search": "heist"}, ["Alpha", "Beta"]),
        ({"sort_by": "price", "order": "desc"}, ["Beta", "Alpha", "Gamma"]),
        ({"search": "heist", "sort_by": "year", "order": "desc"}, ["Beta", "Alpha"]),
    ],
    ids=["filter_year", "filter_imdb", "search", "sort", "search_and_sort"],
)
async def test_list_purchased_applies_catalog_query(
    client: AsyncClient,
    user: User,
    purchased: list[Movie],
    params: dict[str, Any],
    expected: list[str],
) -> None:
    """Same query as the catalog; Delta matches search and filters but is not
    purchased by `user`, so it never appears."""
    response = await client.get(PURCHASED_URL, params=params, headers=auth_header(user))

    assert response.status_code == 200
    assert names(response.json()) == expected
    assert response.json()["total"] == len(expected)


async def test_list_purchased_filters_by_genre(
    client: AsyncClient,
    db_session: AsyncSession,
    user: User,
    catalog: Catalog,
    purchased: list[Movie],
) -> None:
    """All fixture movies are Drama; Gamma also becomes a Comedy here."""
    gamma = await db_session.get(Movie, purchased[2].id, populate_existing=True)
    assert gamma is not None
    await db_session.refresh(gamma, ["genres"])
    gamma.genres.append(catalog.genres[1])
    await db_session.commit()

    response = await client.get(
        PURCHASED_URL,
        params={"genre_id": catalog.genres[1].id},
        headers=auth_header(user),
    )

    assert names(response.json()) == ["Gamma"]
    assert response.json()["total"] == 1


async def test_list_purchased_pagination(
    client: AsyncClient, user: User, purchased: list[Movie]
) -> None:
    response = await client.get(
        PURCHASED_URL, params={"page": 2, "page_size": 2}, headers=auth_header(user)
    )

    body = response.json()
    assert names(body) == ["Gamma"]
    assert body["total"] == 3
    assert body["page"] == 2
    assert body["page_size"] == 2


async def test_list_purchased_loads_genres_eagerly(
    client: AsyncClient, db_session: AsyncSession, user: User, purchased: list[Movie]
) -> None:
    """Nothing is in the identity map: genres must be loaded by the query."""
    db_session.expunge_all()

    response = await client.get(PURCHASED_URL, headers=auth_header(user))

    assert response.status_code == 200
    assert all(item["genres"] for item in response.json()["items"])


@pytest.mark.parametrize(
    "params",
    [{"page": 0}, {"page_size": 101}, {"sort_by": "name"}, {"year_from": 1800}],
    ids=["page_zero", "page_size_too_big", "unknown_sort", "year_too_small"],
)
async def test_list_purchased_invalid_query_returns_422(
    client: AsyncClient, user: User, params: dict[str, Any]
) -> None:
    response = await client.get(PURCHASED_URL, params=params, headers=auth_header(user))

    assert response.status_code == 422
