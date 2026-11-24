"""Two concurrent create_order calls must not create two orders (double submit).

Unlike other DB tests, this one needs two real connections: inside the shared
`db_session` (one connection) SELECT ... FOR UPDATE never waits for itself.
Data is committed for real and removed at teardown.
"""

import asyncio
from collections.abc import AsyncGenerator
from decimal import Decimal

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.accounts.models import User, UserGroup, UserGroupEnum
from src.cart.models import Cart, CartItem
from src.cart.service import list_cart_movies
from src.movies.models import Certification, Movie
from src.orders.exceptions import EmptyCartError
from src.orders.models import Order
from src.orders.service import create_order
from tests.conftest import test_engine

# Long enough for the second call to read the cart too if nothing blocks it.
RACE_WINDOW_SECONDS = 0.3


def new_session() -> AsyncSession:
    """A session with its own connection (not the rolled-back test transaction)."""
    return AsyncSession(test_engine, expire_on_commit=False)


@pytest.fixture
async def user_with_cart(create_schema: None) -> AsyncGenerator[int]:
    """Commit a user with one movie in the cart; yield user id; clean up."""
    async with new_session() as session:
        group = await session.scalar(
            select(UserGroup).where(UserGroup.name == UserGroupEnum.USER)
        )
        user = User(
            email="race@example.com",
            hashed_password="not-used",
            is_active=True,
            group=group,
        )
        certification = Certification(name="Race-PG")
        movie = Movie(
            name="Race Movie",
            year=2020,
            time=100,
            imdb=7.0,
            votes=1000,
            description="Concurrency test.",
            price=Decimal("5.00"),
            certification=certification,
        )
        session.add_all([user, movie])
        await session.flush()
        cart = Cart(user_id=user.id)
        session.add(cart)
        await session.flush()
        session.add(CartItem(cart_id=cart.id, movie_id=movie.id))
        await session.commit()
        user_id, movie_id = user.id, movie.id
        certification_id = certification.id

    yield user_id

    async with new_session() as session:
        # Orders first: order_items -> movies and orders -> users are RESTRICT.
        await session.execute(delete(Order).where(Order.user_id == user_id))
        await session.execute(delete(Cart).where(Cart.user_id == user_id))
        await session.execute(delete(Movie).where(Movie.id == movie_id))
        await session.execute(
            delete(Certification).where(Certification.id == certification_id)
        )
        await session.execute(delete(User).where(User.id == user_id))
        await session.commit()


async def run_create_order(user_id: int) -> object:
    """Run create_order in its own session; return the result or the error."""
    async with new_session() as session:
        try:
            return await create_order(db=session, user_id=user_id)
        except EmptyCartError as exc:
            return exc


async def test_concurrent_create_order_creates_one_order(
    user_with_cart: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def slow_list_cart_movies(db: AsyncSession, user_id: int) -> list[Movie]:
        movies = await list_cart_movies(db=db, user_id=user_id)
        await asyncio.sleep(RACE_WINDOW_SECONDS)  # widen the race window
        return movies

    monkeypatch.setattr("src.orders.service.list_cart_movies", slow_list_cart_movies)

    results = await asyncio.gather(
        run_create_order(user_with_cart), run_create_order(user_with_cart)
    )

    # The second call waited for the cart lock and saw the emptied cart.
    errors = [result for result in results if isinstance(result, EmptyCartError)]
    assert len(errors) == 1
    async with new_session() as session:
        orders_count = await session.scalar(
            select(func.count()).where(Order.user_id == user_with_cart)
        )
    assert orders_count == 1
