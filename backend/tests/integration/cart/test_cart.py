"""Cart of the current user (any logged-in user)."""

from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.accounts.models import User, UserGroupEnum
from src.cart.models import Cart, CartItem
from src.movies.models import Movie
from tests.integration.conftest import (
    UNKNOWN_ID,
    Catalog,
    CreateUser,
    auth_header,
    create_caller,
)

CART_ITEMS_URL = "/api/v1/cart/items"


def cart_item_url(movie_id: int) -> str:
    return f"{CART_ITEMS_URL}/{movie_id}"


async def stored_cart_items(db_session: AsyncSession) -> set[tuple[int, int]]:
    """{(user_id, movie_id)} of all cart items, read from the DB."""
    result = await db_session.execute(
        select(Cart.user_id, CartItem.movie_id).join(
            CartItem, CartItem.cart_id == Cart.id
        )
    )
    return {(user_id, movie_id) for user_id, movie_id in result.all()}


async def count_carts(db_session: AsyncSession) -> int:
    result = await db_session.execute(select(func.count()).select_from(Cart))
    return result.scalar_one()


@pytest.fixture
async def user(create_user: CreateUser) -> User:
    return await create_caller(create_user, group=UserGroupEnum.USER)


@pytest.fixture
async def other_user(create_user: CreateUser) -> User:
    return await create_user(
        email="other@example.com", is_active=True, token_expires_in=None
    )


@pytest.fixture
async def other_movie(db_session: AsyncSession, catalog: Catalog) -> Movie:
    result = Movie(
        name="Interstellar",
        year=2014,
        time=169,
        imdb=8.7,
        votes=2000000,
        description="Explorers travel through a wormhole in space.",
        price=Decimal("9.99"),
        certification=catalog.certification,
    )
    db_session.add(result)
    await db_session.commit()
    return result


# --- access control ---


async def test_get_cart_requires_token(client: AsyncClient) -> None:
    response = await client.get(CART_ITEMS_URL)

    assert response.status_code == 401


@pytest.mark.parametrize("method", ["PUT", "DELETE"])
async def test_cart_item_requires_token(
    client: AsyncClient, movie: Movie, method: str
) -> None:
    response = await client.request(method, cart_item_url(movie.id))

    assert response.status_code == 401


# --- add ---


async def test_add_movie(
    client: AsyncClient, db_session: AsyncSession, user: User, movie: Movie
) -> None:
    response = await client.put(cart_item_url(movie.id), headers=auth_header(user))

    assert response.status_code == 204
    assert response.content == b""
    assert await stored_cart_items(db_session) == {(user.id, movie.id)}


async def test_add_creates_cart_on_first_movie(
    client: AsyncClient, db_session: AsyncSession, user: User, movie: Movie
) -> None:
    assert await count_carts(db_session) == 0

    await client.put(cart_item_url(movie.id), headers=auth_header(user))

    cart = await db_session.scalar(select(Cart).where(Cart.user_id == user.id))
    assert cart is not None


async def test_add_same_movie_twice_is_idempotent(
    client: AsyncClient, db_session: AsyncSession, user: User, movie: Movie
) -> None:
    await client.put(cart_item_url(movie.id), headers=auth_header(user))
    response = await client.put(cart_item_url(movie.id), headers=auth_header(user))

    assert response.status_code == 204
    assert await stored_cart_items(db_session) == {(user.id, movie.id)}
    assert await count_carts(db_session) == 1


async def test_add_two_movies_uses_one_cart(
    client: AsyncClient,
    db_session: AsyncSession,
    user: User,
    movie: Movie,
    other_movie: Movie,
) -> None:
    await client.put(cart_item_url(movie.id), headers=auth_header(user))
    await client.put(cart_item_url(other_movie.id), headers=auth_header(user))

    assert await stored_cart_items(db_session) == {
        (user.id, movie.id),
        (user.id, other_movie.id),
    }
    assert await count_carts(db_session) == 1


async def test_add_by_two_users_creates_separate_carts(
    client: AsyncClient,
    db_session: AsyncSession,
    user: User,
    other_user: User,
    movie: Movie,
) -> None:
    await client.put(cart_item_url(movie.id), headers=auth_header(user))
    await client.put(cart_item_url(movie.id), headers=auth_header(other_user))

    assert await stored_cart_items(db_session) == {
        (user.id, movie.id),
        (other_user.id, movie.id),
    }
    assert await count_carts(db_session) == 2


async def test_add_unknown_movie_returns_404(
    client: AsyncClient, db_session: AsyncSession, user: User
) -> None:
    response = await client.put(cart_item_url(UNKNOWN_ID), headers=auth_header(user))

    assert response.status_code == 404
    assert response.json() == {"detail": "Movie not found."}
    assert await count_carts(db_session) == 0


@pytest.mark.parametrize("method", ["PUT", "DELETE"])
async def test_cart_item_with_non_integer_id_returns_422(
    client: AsyncClient, user: User, method: str
) -> None:
    response = await client.request(
        method, f"{CART_ITEMS_URL}/abc", headers=auth_header(user)
    )

    assert response.status_code == 422


# --- remove ---


async def test_remove_movie(
    client: AsyncClient,
    db_session: AsyncSession,
    user: User,
    movie: Movie,
    other_movie: Movie,
) -> None:
    await client.put(cart_item_url(movie.id), headers=auth_header(user))
    await client.put(cart_item_url(other_movie.id), headers=auth_header(user))

    response = await client.delete(cart_item_url(movie.id), headers=auth_header(user))

    assert response.status_code == 204
    assert response.content == b""
    assert await stored_cart_items(db_session) == {(user.id, other_movie.id)}


async def test_remove_last_movie_keeps_empty_cart(
    client: AsyncClient, db_session: AsyncSession, user: User, movie: Movie
) -> None:
    await client.put(cart_item_url(movie.id), headers=auth_header(user))

    await client.delete(cart_item_url(movie.id), headers=auth_header(user))

    assert await stored_cart_items(db_session) == set()
    assert await count_carts(db_session) == 1


async def test_remove_only_from_own_cart(
    client: AsyncClient,
    db_session: AsyncSession,
    user: User,
    other_user: User,
    movie: Movie,
) -> None:
    await client.put(cart_item_url(movie.id), headers=auth_header(user))
    await client.put(cart_item_url(movie.id), headers=auth_header(other_user))

    await client.delete(cart_item_url(movie.id), headers=auth_header(user))

    assert await stored_cart_items(db_session) == {(other_user.id, movie.id)}


async def test_remove_movie_not_in_cart_is_idempotent(
    client: AsyncClient,
    db_session: AsyncSession,
    user: User,
    movie: Movie,
    other_movie: Movie,
) -> None:
    await client.put(cart_item_url(movie.id), headers=auth_header(user))

    response = await client.delete(
        cart_item_url(other_movie.id), headers=auth_header(user)
    )

    assert response.status_code == 204
    assert await stored_cart_items(db_session) == {(user.id, movie.id)}


@pytest.mark.parametrize("known_movie", [True, False], ids=["movie", "unknown_movie"])
async def test_remove_without_cart_does_not_create_it(
    client: AsyncClient,
    db_session: AsyncSession,
    user: User,
    movie: Movie,
    known_movie: bool,
) -> None:
    movie_id = movie.id if known_movie else UNKNOWN_ID

    response = await client.delete(cart_item_url(movie_id), headers=auth_header(user))

    assert response.status_code == 204
    assert await count_carts(db_session) == 0


# --- view ---


async def test_get_cart_without_cart_returns_empty_list(
    client: AsyncClient, db_session: AsyncSession, user: User
) -> None:
    response = await client.get(CART_ITEMS_URL, headers=auth_header(user))

    assert response.status_code == 200
    assert response.json() == {"items": []}
    assert await count_carts(db_session) == 0


async def test_get_cart_returns_movie_fields(
    client: AsyncClient,
    db_session: AsyncSession,
    user: User,
    movie: Movie,
    catalog: Catalog,
) -> None:
    await client.put(cart_item_url(movie.id), headers=auth_header(user))
    # Fresh session state: catches a missing eager load of genres.
    db_session.expunge_all()

    response = await client.get(CART_ITEMS_URL, headers=auth_header(user))

    assert response.status_code == 200
    genre = catalog.genres[0]
    assert response.json() == {
        "items": [
            {
                "id": movie.id,
                "name": "Inception",
                "year": 2010,
                "price": "7.99",
                "genres": [{"id": genre.id, "name": genre.name}],
            }
        ]
    }


async def test_get_cart_movie_without_genres(
    client: AsyncClient, user: User, other_movie: Movie
) -> None:
    await client.put(cart_item_url(other_movie.id), headers=auth_header(user))

    response = await client.get(CART_ITEMS_URL, headers=auth_header(user))

    assert response.json()["items"][0]["genres"] == []


async def test_get_cart_ordered_by_addition(
    client: AsyncClient, user: User, movie: Movie, other_movie: Movie
) -> None:
    await client.put(cart_item_url(other_movie.id), headers=auth_header(user))
    await client.put(cart_item_url(movie.id), headers=auth_header(user))

    response = await client.get(CART_ITEMS_URL, headers=auth_header(user))

    ids = [item["id"] for item in response.json()["items"]]
    assert ids == [other_movie.id, movie.id]


async def test_get_cart_shows_only_own_movies(
    client: AsyncClient,
    user: User,
    other_user: User,
    movie: Movie,
    other_movie: Movie,
) -> None:
    await client.put(cart_item_url(movie.id), headers=auth_header(user))
    await client.put(cart_item_url(other_movie.id), headers=auth_header(other_user))

    response = await client.get(CART_ITEMS_URL, headers=auth_header(user))

    ids = [item["id"] for item in response.json()["items"]]
    assert ids == [movie.id]


async def test_get_cart_after_removing_last_movie_is_empty(
    client: AsyncClient, user: User, movie: Movie
) -> None:
    await client.put(cart_item_url(movie.id), headers=auth_header(user))
    await client.delete(cart_item_url(movie.id), headers=auth_header(user))

    response = await client.get(CART_ITEMS_URL, headers=auth_header(user))

    assert response.json() == {"items": []}
