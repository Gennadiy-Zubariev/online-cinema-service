"""Order creation from the current user's cart (any logged-in user)."""

from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.accounts.models import User, UserGroupEnum
from src.cart.models import Cart, CartItem
from src.movies.models import Movie, PurchasedMovie
from src.orders.models import Order, OrderItem, OrderStatusEnum
from tests.integration.conftest import (
    Catalog,
    CreateUser,
    auth_header,
    create_caller,
)

ORDERS_URL = "/api/v1/orders"


async def fill_cart(db_session: AsyncSession, user: User, *movies: Movie) -> None:
    """Create the user's cart with movies in the given order (bypasses the API)."""
    cart = Cart(user_id=user.id)
    db_session.add(cart)
    await db_session.flush()
    db_session.add_all([CartItem(cart_id=cart.id, movie_id=m.id) for m in movies])
    await db_session.commit()


async def stored_cart_movie_ids(db_session: AsyncSession, user: User) -> set[int]:
    result = await db_session.scalars(
        select(CartItem.movie_id)
        .join(Cart, Cart.id == CartItem.cart_id)
        .where(Cart.user_id == user.id)
    )
    return set(result.all())


async def count_orders(db_session: AsyncSession) -> int:
    result = await db_session.execute(select(func.count()).select_from(Order))
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


async def test_create_order_requires_token(client: AsyncClient) -> None:
    response = await client.post(ORDERS_URL)

    assert response.status_code == 401


# --- success ---


async def test_create_order(
    client: AsyncClient, db_session: AsyncSession, user: User, movie: Movie
) -> None:
    await fill_cart(db_session, user, movie)

    response = await client.post(ORDERS_URL, headers=auth_header(user))

    assert response.status_code == 201
    body = response.json()
    assert isinstance(body["id"], int)
    assert body["created_at"] is not None
    assert body["status"] == "pending"
    assert body["total_amount"] == "7.99"
    assert len(body["items"]) == 1
    item = body["items"][0]
    assert isinstance(item["id"], int)
    assert item["movie"] == {"id": movie.id, "name": "Inception"}
    assert item["price_at_order"] == "7.99"
    assert body["excluded_movies"] == []
    assert "user_id" not in body


async def test_create_order_stores_order_in_db(
    client: AsyncClient, db_session: AsyncSession, user: User, movie: Movie
) -> None:
    await fill_cart(db_session, user, movie)

    response = await client.post(ORDERS_URL, headers=auth_header(user))

    order_id = response.json()["id"]
    order = await db_session.scalar(select(Order).where(Order.id == order_id))
    assert order is not None
    assert order.user_id == user.id
    assert order.status == "pending"
    assert order.total_amount == Decimal("7.99")
    stored_items = await db_session.execute(
        select(OrderItem.movie_id, OrderItem.price_at_order).where(
            OrderItem.order_id == order_id
        )
    )
    assert stored_items.all() == [(movie.id, Decimal("7.99"))]


async def test_create_order_with_several_movies(
    client: AsyncClient,
    db_session: AsyncSession,
    user: User,
    movie: Movie,
    other_movie: Movie,
) -> None:
    await fill_cart(db_session, user, other_movie, movie)

    response = await client.post(ORDERS_URL, headers=auth_header(user))

    body = response.json()
    assert body["total_amount"] == "17.98"
    # items keep the cart order (order of adding)
    assert [item["movie"]["name"] for item in body["items"]] == [
        "Interstellar",
        "Inception",
    ]
    assert [item["price_at_order"] for item in body["items"]] == ["9.99", "7.99"]


async def test_create_order_clears_ordered_movies_from_cart(
    client: AsyncClient,
    db_session: AsyncSession,
    user: User,
    movie: Movie,
    other_movie: Movie,
) -> None:
    await fill_cart(db_session, user, movie, other_movie)

    await client.post(ORDERS_URL, headers=auth_header(user))

    assert await stored_cart_movie_ids(db_session, user) == set()


async def test_create_order_keeps_other_users_cart(
    client: AsyncClient,
    db_session: AsyncSession,
    user: User,
    other_user: User,
    movie: Movie,
) -> None:
    await fill_cart(db_session, user, movie)
    await fill_cart(db_session, other_user, movie)

    await client.post(ORDERS_URL, headers=auth_header(user))

    assert await stored_cart_movie_ids(db_session, other_user) == {movie.id}


async def test_create_order_price_is_snapshot(
    client: AsyncClient, db_session: AsyncSession, user: User, movie: Movie
) -> None:
    await fill_cart(db_session, user, movie)
    response = await client.post(ORDERS_URL, headers=auth_header(user))

    movie.price = Decimal("19.99")
    await db_session.commit()

    price = await db_session.scalar(
        select(OrderItem.price_at_order).where(
            OrderItem.order_id == response.json()["id"]
        )
    )
    assert price == Decimal("7.99")


async def test_second_order_after_success_returns_400(
    client: AsyncClient, db_session: AsyncSession, user: User, movie: Movie
) -> None:
    await fill_cart(db_session, user, movie)
    await client.post(ORDERS_URL, headers=auth_header(user))

    response = await client.post(ORDERS_URL, headers=auth_header(user))

    assert response.status_code == 400
    assert response.json() == {"detail": "Cart is empty."}
    assert await count_orders(db_session) == 1


# --- purchased movies ---


async def test_create_order_excludes_purchased_movies(
    client: AsyncClient,
    db_session: AsyncSession,
    user: User,
    movie: Movie,
    other_movie: Movie,
) -> None:
    await fill_cart(db_session, user, movie, other_movie)
    db_session.add(PurchasedMovie(user_id=user.id, movie_id=movie.id))
    await db_session.commit()

    response = await client.post(ORDERS_URL, headers=auth_header(user))

    assert response.status_code == 201
    body = response.json()
    assert [item["movie"]["id"] for item in body["items"]] == [other_movie.id]
    assert body["total_amount"] == "9.99"
    assert body["excluded_movies"] == [{"id": movie.id, "name": "Inception"}]
    # both ordered and excluded movies leave the cart
    assert await stored_cart_movie_ids(db_session, user) == set()


async def test_movie_purchased_by_other_user_is_not_excluded(
    client: AsyncClient,
    db_session: AsyncSession,
    user: User,
    other_user: User,
    movie: Movie,
) -> None:
    await fill_cart(db_session, user, movie)
    db_session.add(PurchasedMovie(user_id=other_user.id, movie_id=movie.id))
    await db_session.commit()

    response = await client.post(ORDERS_URL, headers=auth_header(user))

    body = response.json()
    assert [item["movie"]["id"] for item in body["items"]] == [movie.id]
    assert body["excluded_movies"] == []


# --- errors ---


async def test_create_order_without_cart_returns_400(
    client: AsyncClient, db_session: AsyncSession, user: User
) -> None:
    response = await client.post(ORDERS_URL, headers=auth_header(user))

    assert response.status_code == 400
    assert response.json() == {"detail": "Cart is empty."}
    assert await count_orders(db_session) == 0


async def test_create_order_with_empty_cart_returns_400(
    client: AsyncClient, db_session: AsyncSession, user: User
) -> None:
    await fill_cart(db_session, user)

    response = await client.post(ORDERS_URL, headers=auth_header(user))

    assert response.status_code == 400
    assert response.json() == {"detail": "Cart is empty."}


async def test_other_users_cart_is_not_used(
    client: AsyncClient,
    db_session: AsyncSession,
    user: User,
    other_user: User,
    movie: Movie,
) -> None:
    await fill_cart(db_session, other_user, movie)

    response = await client.post(ORDERS_URL, headers=auth_header(user))

    assert response.status_code == 400
    assert response.json() == {"detail": "Cart is empty."}


async def test_all_movies_purchased_returns_400(
    client: AsyncClient,
    db_session: AsyncSession,
    user: User,
    movie: Movie,
    other_movie: Movie,
) -> None:
    await fill_cart(db_session, user, movie, other_movie)
    db_session.add_all(
        [
            PurchasedMovie(user_id=user.id, movie_id=movie.id),
            PurchasedMovie(user_id=user.id, movie_id=other_movie.id),
        ]
    )
    await db_session.commit()

    response = await client.post(ORDERS_URL, headers=auth_header(user))

    assert response.status_code == 400
    assert response.json() == {
        "detail": "All movies in the cart are already purchased."
    }
    assert await count_orders(db_session) == 0
    # nothing is written: purchased movies stay in the cart
    assert await stored_cart_movie_ids(db_session, user) == {
        movie.id,
        other_movie.id,
    }


# --- list of own orders ---


async def save_order(
    db_session: AsyncSession,
    user: User,
    *movies: Movie,
    status: OrderStatusEnum = OrderStatusEnum.PENDING,
) -> Order:
    """Save an order directly in the DB (bypasses the cart and the API)."""
    order = Order(
        user_id=user.id,
        status=status,
        total_amount=sum(movie.price for movie in movies),
        items=[OrderItem(movie=m, price_at_order=m.price) for m in movies],
    )
    db_session.add(order)
    await db_session.commit()
    return order


async def test_list_orders_requires_token(client: AsyncClient) -> None:
    response = await client.get(ORDERS_URL)

    assert response.status_code == 401


async def test_list_orders_empty(client: AsyncClient, user: User) -> None:
    response = await client.get(ORDERS_URL, headers=auth_header(user))

    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0, "page": 1, "page_size": 20}


async def test_list_orders_fields(
    client: AsyncClient,
    db_session: AsyncSession,
    user: User,
    movie: Movie,
    other_movie: Movie,
) -> None:
    order = await save_order(
        db_session, user, movie, other_movie, status=OrderStatusEnum.PAID
    )

    response = await client.get(ORDERS_URL, headers=auth_header(user))

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    item = body["items"][0]
    assert item["id"] == order.id
    assert item["created_at"] is not None
    assert item["status"] == "paid"
    assert item["total_amount"] == "17.98"
    assert [(i["movie"], i["price_at_order"]) for i in item["items"]] == [
        ({"id": movie.id, "name": "Inception"}, "7.99"),
        ({"id": other_movie.id, "name": "Interstellar"}, "9.99"),
    ]
    assert "excluded_movies" not in item
    assert "user_id" not in item


async def test_list_orders_shows_only_own(
    client: AsyncClient,
    db_session: AsyncSession,
    user: User,
    other_user: User,
    movie: Movie,
) -> None:
    own = await save_order(db_session, user, movie)
    await save_order(db_session, other_user, movie)

    response = await client.get(ORDERS_URL, headers=auth_header(user))

    body = response.json()
    assert [order["id"] for order in body["items"]] == [own.id]
    assert body["total"] == 1


async def test_list_orders_newest_first(
    client: AsyncClient, db_session: AsyncSession, user: User, movie: Movie
) -> None:
    first = await save_order(db_session, user, movie)
    second = await save_order(db_session, user, movie)
    third = await save_order(db_session, user, movie)

    response = await client.get(ORDERS_URL, headers=auth_header(user))

    ids = [order["id"] for order in response.json()["items"]]
    assert ids == [third.id, second.id, first.id]


async def test_list_orders_pagination(
    client: AsyncClient, db_session: AsyncSession, user: User, movie: Movie
) -> None:
    orders = [await save_order(db_session, user, movie) for _ in range(3)]

    response = await client.get(
        ORDERS_URL, params={"page": 2, "page_size": 2}, headers=auth_header(user)
    )

    body = response.json()
    assert [order["id"] for order in body["items"]] == [orders[0].id]
    assert body["total"] == 3
    assert body["page"] == 2
    assert body["page_size"] == 2


async def test_list_orders_loads_items_eagerly(
    client: AsyncClient,
    db_session: AsyncSession,
    user: User,
    movie: Movie,
    other_movie: Movie,
) -> None:
    """Nothing is in the identity map: items and movies must be eager-loaded."""
    await save_order(db_session, user, movie, other_movie)
    db_session.expunge_all()

    response = await client.get(ORDERS_URL, headers=auth_header(user))

    assert response.status_code == 200
    names = [i["movie"]["name"] for i in response.json()["items"][0]["items"]]
    assert names == ["Inception", "Interstellar"]


@pytest.mark.parametrize(
    "params", [{"page": 0}, {"page_size": 0}, {"page_size": 101}, {"page": "abc"}]
)
async def test_list_orders_invalid_pagination_returns_422(
    client: AsyncClient, user: User, params: dict[str, int | str]
) -> None:
    response = await client.get(ORDERS_URL, params=params, headers=auth_header(user))

    assert response.status_code == 422
