from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.accounts.models import User, UserGroup, UserGroupEnum
from src.config.settings import get_settings
from src.movies.models import Certification, Movie
from src.orders.models import Order, OrderItem, OrderStatusEnum
from src.tasks.orders import delete_expired_pending_orders

settings = get_settings()

EXPIRED_AGE = timedelta(days=settings.PENDING_ORDER_EXPIRE_DAYS, minutes=1)
FRESH_AGE = timedelta(days=settings.PENDING_ORDER_EXPIRE_DAYS, minutes=-1)


@pytest.fixture
def user(sync_db_session: Session) -> User:
    group = sync_db_session.scalar(
        select(UserGroup).where(UserGroup.name == UserGroupEnum.USER)
    )
    result = User(email="user@example.com", hashed_password="not-a-hash", group=group)
    sync_db_session.add(result)
    sync_db_session.commit()
    return result


@pytest.fixture
def movie(sync_db_session: Session) -> Movie:
    result = Movie(
        name="Inception",
        year=2010,
        time=148,
        imdb=8.8,
        votes=2500000,
        description="A thief who steals corporate secrets through dreams.",
        price=Decimal("7.99"),
        certification=Certification(name="PG-13"),
    )
    sync_db_session.add(result)
    sync_db_session.commit()
    return result


def create_order(
    session: Session,
    user: User,
    movie: Movie,
    status: OrderStatusEnum,
    age: timedelta,
) -> Order:
    order = Order(
        user_id=user.id,
        status=status,
        created_at=datetime.now(UTC) - age,
        total_amount=movie.price,
        items=[OrderItem(movie=movie, price_at_order=movie.price)],
    )
    session.add(order)
    session.commit()
    return order


def stored_order_ids(session: Session) -> list[int]:
    return list(session.scalars(select(Order.id).order_by(Order.id)).all())


def test_deletes_expired_pending_order(
    sync_db_session: Session, user: User, movie: Movie
) -> None:
    create_order(sync_db_session, user, movie, OrderStatusEnum.PENDING, EXPIRED_AGE)

    delete_expired_pending_orders(sync_db_session, settings)

    assert stored_order_ids(sync_db_session) == []


def test_deletes_items_of_expired_order(
    sync_db_session: Session, user: User, movie: Movie
) -> None:
    create_order(sync_db_session, user, movie, OrderStatusEnum.PENDING, EXPIRED_AGE)

    delete_expired_pending_orders(sync_db_session, settings)

    # ON DELETE CASCADE on order_items.order_id
    assert sync_db_session.scalars(select(OrderItem.id)).all() == []


def test_keeps_fresh_pending_order(
    sync_db_session: Session, user: User, movie: Movie
) -> None:
    order = create_order(
        sync_db_session, user, movie, OrderStatusEnum.PENDING, FRESH_AGE
    )

    delete_expired_pending_orders(sync_db_session, settings)

    assert stored_order_ids(sync_db_session) == [order.id]


@pytest.mark.parametrize("status", [OrderStatusEnum.PAID, OrderStatusEnum.CANCELED])
def test_keeps_old_order_that_is_not_pending(
    sync_db_session: Session, user: User, movie: Movie, status: OrderStatusEnum
) -> None:
    order = create_order(sync_db_session, user, movie, status, EXPIRED_AGE)

    delete_expired_pending_orders(sync_db_session, settings)

    assert stored_order_ids(sync_db_session) == [order.id]


def test_deletes_only_expired_among_several(
    sync_db_session: Session, user: User, movie: Movie
) -> None:
    create_order(sync_db_session, user, movie, OrderStatusEnum.PENDING, EXPIRED_AGE)
    fresh = create_order(
        sync_db_session, user, movie, OrderStatusEnum.PENDING, FRESH_AGE
    )
    paid = create_order(sync_db_session, user, movie, OrderStatusEnum.PAID, EXPIRED_AGE)

    delete_expired_pending_orders(sync_db_session, settings)

    assert stored_order_ids(sync_db_session) == [fresh.id, paid.id]


def test_expire_days_come_from_settings(
    sync_db_session: Session, user: User, movie: Movie
) -> None:
    order = create_order(
        sync_db_session, user, movie, OrderStatusEnum.PENDING, timedelta(days=2)
    )
    one_day = settings.model_copy(update={"PENDING_ORDER_EXPIRE_DAYS": 1})

    delete_expired_pending_orders(sync_db_session, settings)
    assert stored_order_ids(sync_db_session) == [order.id]

    delete_expired_pending_orders(sync_db_session, one_day)
    assert stored_order_ids(sync_db_session) == []


def test_keeps_movie_and_user(
    sync_db_session: Session, user: User, movie: Movie
) -> None:
    create_order(sync_db_session, user, movie, OrderStatusEnum.PENDING, EXPIRED_AGE)

    delete_expired_pending_orders(sync_db_session, settings)

    assert sync_db_session.get(Movie, movie.id) is not None
    assert sync_db_session.get(User, user.id) is not None
