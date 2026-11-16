"""Start paying for an order via Stripe Checkout (Stripe is faked)."""

from dataclasses import dataclass, field
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.accounts.models import User
from src.movies.models import Movie
from src.orders.models import Order, OrderItem, OrderStatusEnum
from src.payments import service as payments_service
from tests.integration.conftest import UNKNOWN_ID, auth_header
from tests.integration.payments.conftest import (
    purchase,
    save_order,
    stored_order,
)

CHECKOUT_URL = "https://checkout.stripe.test/c/pay/cs_test_123"


def checkout_url(order_id: int | str) -> str:
    return f"/api/v1/orders/{order_id}/checkout"


@dataclass
class FakeStripe:
    """Records what would be sent to Stripe instead of calling it."""

    calls: list[tuple[int, list[tuple[str, Decimal]]]] = field(default_factory=list)

    def create_checkout_session(self, order_id: int, items: list[OrderItem]) -> str:
        # item.movie.name is read here, in a worker thread: it must be loaded
        self.calls.append(
            (order_id, [(item.movie.name, item.price_at_order) for item in items])
        )
        return CHECKOUT_URL


@pytest.fixture
def fake_stripe(monkeypatch: pytest.MonkeyPatch) -> FakeStripe:
    fake = FakeStripe()
    monkeypatch.setattr(
        payments_service, "create_checkout_session", fake.create_checkout_session
    )
    return fake


async def stored_item_movie_ids(db_session: AsyncSession, order_id: int) -> list[int]:
    result = await db_session.scalars(
        select(OrderItem.movie_id)
        .where(OrderItem.order_id == order_id)
        .order_by(OrderItem.id)
    )
    return list(result.all())


# --- access control ---


async def test_checkout_requires_token(
    client: AsyncClient, fake_stripe: FakeStripe
) -> None:
    response = await client.post(checkout_url(1))

    assert response.status_code == 401
    assert fake_stripe.calls == []


# --- success ---


async def test_checkout_returns_stripe_url(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_stripe: FakeStripe,
    user: User,
    movie: Movie,
    other_movie: Movie,
) -> None:
    order = await save_order(db_session, user, movie, other_movie)

    response = await client.post(checkout_url(order.id), headers=auth_header(user))

    assert response.status_code == 200
    assert response.json() == {"checkout_url": CHECKOUT_URL}
    assert fake_stripe.calls == [
        (
            order.id,
            [("Inception", Decimal("7.99")), ("Interstellar", Decimal("9.99"))],
        )
    ]


async def test_checkout_without_purchased_movies_keeps_order(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_stripe: FakeStripe,
    user: User,
    movie: Movie,
    other_movie: Movie,
) -> None:
    order = await save_order(db_session, user, movie, other_movie)

    await client.post(checkout_url(order.id), headers=auth_header(user))

    stored = await stored_order(db_session, order.id)
    assert stored.status == OrderStatusEnum.PENDING
    assert stored.total_amount == Decimal("17.98")
    assert await stored_item_movie_ids(db_session, order.id) == [
        movie.id,
        other_movie.id,
    ]


async def test_checkout_sends_price_at_order_not_current_price(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_stripe: FakeStripe,
    user: User,
    movie: Movie,
) -> None:
    order = await save_order(db_session, user, movie)
    movie.price = Decimal("19.99")
    await db_session.commit()

    await client.post(checkout_url(order.id), headers=auth_header(user))

    assert fake_stripe.calls == [(order.id, [("Inception", Decimal("7.99"))])]


async def test_checkout_loads_items_eagerly(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_stripe: FakeStripe,
    user: User,
    movie: Movie,
) -> None:
    """Nothing is in the identity map: items and movies must be eager-loaded."""
    order = await save_order(db_session, user, movie)
    db_session.expunge_all()

    response = await client.post(checkout_url(order.id), headers=auth_header(user))

    assert response.status_code == 200
    assert fake_stripe.calls == [(order.id, [("Inception", Decimal("7.99"))])]


async def test_checkout_can_be_repeated(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_stripe: FakeStripe,
    user: User,
    movie: Movie,
) -> None:
    """Closing the Stripe page and paying again creates a new session."""
    order = await save_order(db_session, user, movie)

    await client.post(checkout_url(order.id), headers=auth_header(user))
    response = await client.post(checkout_url(order.id), headers=auth_header(user))

    assert response.status_code == 200
    assert len(fake_stripe.calls) == 2


# --- purchased movies ---


async def test_checkout_removes_purchased_movies(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_stripe: FakeStripe,
    user: User,
    movie: Movie,
    other_movie: Movie,
) -> None:
    order = await save_order(db_session, user, movie, other_movie)
    await purchase(db_session, user, movie)

    response = await client.post(checkout_url(order.id), headers=auth_header(user))

    assert response.status_code == 200
    # only the remaining movie goes to Stripe
    assert fake_stripe.calls == [(order.id, [("Interstellar", Decimal("9.99"))])]
    stored = await stored_order(db_session, order.id)
    assert stored.status == OrderStatusEnum.PENDING
    assert stored.total_amount == Decimal("9.99")
    assert await stored_item_movie_ids(db_session, order.id) == [other_movie.id]


async def test_checkout_keeps_movie_purchased_by_other_user(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_stripe: FakeStripe,
    user: User,
    other_user: User,
    movie: Movie,
) -> None:
    order = await save_order(db_session, user, movie)
    await purchase(db_session, other_user, movie)

    response = await client.post(checkout_url(order.id), headers=auth_header(user))

    assert response.status_code == 200
    assert fake_stripe.calls == [(order.id, [("Inception", Decimal("7.99"))])]
    assert await stored_item_movie_ids(db_session, order.id) == [movie.id]


async def test_checkout_removes_purchased_movie_only_from_this_order(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_stripe: FakeStripe,
    user: User,
    movie: Movie,
    other_movie: Movie,
) -> None:
    order = await save_order(db_session, user, movie, other_movie)
    paid_order = await save_order(db_session, user, movie, status=OrderStatusEnum.PAID)
    await purchase(db_session, user, movie)

    await client.post(checkout_url(order.id), headers=auth_header(user))

    assert await stored_item_movie_ids(db_session, paid_order.id) == [movie.id]


async def test_checkout_all_movies_purchased_cancels_order(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_stripe: FakeStripe,
    user: User,
    movie: Movie,
    other_movie: Movie,
) -> None:
    order = await save_order(db_session, user, movie, other_movie)
    await purchase(db_session, user, movie, other_movie)

    response = await client.post(checkout_url(order.id), headers=auth_header(user))

    assert response.status_code == 400
    assert response.json() == {
        "detail": "All movies in the order are already purchased. "
        "The order is canceled."
    }
    assert fake_stripe.calls == []
    stored = await stored_order(db_session, order.id)
    assert stored.status == OrderStatusEnum.CANCELED
    # items stay as order history
    assert await stored_item_movie_ids(db_session, order.id) == [
        movie.id,
        other_movie.id,
    ]


# --- errors ---


async def test_checkout_unknown_order_returns_404(
    client: AsyncClient, fake_stripe: FakeStripe, user: User
) -> None:
    response = await client.post(checkout_url(UNKNOWN_ID), headers=auth_header(user))

    assert response.status_code == 404
    assert response.json() == {"detail": "Order not found."}
    assert fake_stripe.calls == []


async def test_checkout_other_users_order_returns_404(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_stripe: FakeStripe,
    user: User,
    other_user: User,
    movie: Movie,
) -> None:
    order = await save_order(db_session, other_user, movie)

    response = await client.post(checkout_url(order.id), headers=auth_header(user))

    assert response.status_code == 404
    assert response.json() == {"detail": "Order not found."}
    assert fake_stripe.calls == []


@pytest.mark.parametrize("status", [OrderStatusEnum.PAID, OrderStatusEnum.CANCELED])
async def test_checkout_not_pending_order_returns_409(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_stripe: FakeStripe,
    user: User,
    movie: Movie,
    status: OrderStatusEnum,
) -> None:
    order = await save_order(db_session, user, movie, status=status)

    response = await client.post(checkout_url(order.id), headers=auth_header(user))

    assert response.status_code == 409
    assert response.json() == {"detail": "Only pending orders can be paid."}
    assert fake_stripe.calls == []


async def test_checkout_invalid_order_id_returns_422(
    client: AsyncClient, fake_stripe: FakeStripe, user: User
) -> None:
    response = await client.post(checkout_url("abc"), headers=auth_header(user))

    assert response.status_code == 422
