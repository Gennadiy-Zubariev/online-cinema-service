"""Fixtures and helpers shared by checkout and webhook tests."""

from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.accounts.models import User, UserGroupEnum
from src.movies.models import Movie, PurchasedMovie
from src.orders.models import Order, OrderItem, OrderStatusEnum
from tests.integration.conftest import Catalog, CreateUser, create_caller


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


async def save_order(
    db_session: AsyncSession,
    user: User,
    *movies: Movie,
    status: OrderStatusEnum = OrderStatusEnum.PENDING,
) -> Order:
    order = Order(
        user_id=user.id,
        status=status,
        total_amount=sum((movie.price for movie in movies), Decimal(0)),
        items=[OrderItem(movie=m, price_at_order=m.price) for m in movies],
    )
    db_session.add(order)
    await db_session.commit()
    return order


async def purchase(db_session: AsyncSession, user: User, *movies: Movie) -> None:
    db_session.add_all(
        [PurchasedMovie(user_id=user.id, movie_id=movie.id) for movie in movies]
    )
    await db_session.commit()


async def stored_order(db_session: AsyncSession, order_id: int) -> Order:
    """Order re-read from the DB (not the stale object from the identity map)."""
    db_session.expunge_all()
    order = await db_session.scalar(select(Order).where(Order.id == order_id))
    assert order is not None
    return order
