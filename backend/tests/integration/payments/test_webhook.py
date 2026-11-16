"""Stripe webhook: signature check and checkout session events.

Events are signed with the real STRIPE_WEBHOOK_SECRET the same way Stripe does
it, so `parse_webhook_event` runs unmocked (no network: HMAC is local).
"""

import hashlib
import hmac
import json
import logging
import time
from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.accounts.models import User
from src.config.settings import get_settings
from src.movies.models import Movie, PurchasedMovie
from src.orders.models import OrderStatusEnum
from src.payments.models import Payment, PaymentStatusEnum
from tests.integration.conftest import UNKNOWN_ID
from tests.integration.payments.conftest import (
    purchase,
    save_order,
    stored_order,
)

WEBHOOK_URL = "/api/v1/payments/webhook"
SESSION_ID = "cs_test_123"
COMPLETED = "checkout.session.completed"
EXPIRED = "checkout.session.expired"
INVALID_SIGNATURE = {"detail": "Invalid webhook signature."}


def checkout_event(
    event_type: str,
    order_id: int,
    *,
    session_id: str = SESSION_ID,
    amount_total: int = 799,
    payment_status: str = "paid",
) -> dict[str, Any]:
    """Minimal Stripe event with a Checkout Session inside."""
    return {
        "id": "evt_test_123",
        "object": "event",
        "type": event_type,
        "data": {
            "object": {
                "id": session_id,
                "object": "checkout.session",
                "amount_total": amount_total,
                "payment_status": payment_status,
                "metadata": {"order_id": str(order_id)},
            }
        },
    }


def sign(
    payload: bytes, *, secret: str | None = None, timestamp: int | None = None
) -> str:
    """Stripe-Signature header: HMAC-SHA256 of "timestamp.payload"."""
    if secret is None:
        secret = get_settings().STRIPE_WEBHOOK_SECRET.get_secret_value()
    if timestamp is None:
        timestamp = int(time.time())
    signed = f"{timestamp}.".encode() + payload
    signature = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={signature}"


async def send_event(client: AsyncClient, event: dict[str, Any]) -> Response:
    payload = json.dumps(event).encode()
    return await client.post(
        WEBHOOK_URL, content=payload, headers={"Stripe-Signature": sign(payload)}
    )


async def stored_payments(db_session: AsyncSession) -> list[Payment]:
    db_session.expunge_all()
    result = await db_session.scalars(select(Payment).order_by(Payment.id))
    return list(result.all())


async def stored_purchased_ids(db_session: AsyncSession, user: User) -> set[int]:
    result = await db_session.scalars(
        select(PurchasedMovie.movie_id).where(PurchasedMovie.user_id == user.id)
    )
    return set(result.all())


# --- signature ---


async def test_webhook_without_signature_returns_400(
    client: AsyncClient, db_session: AsyncSession, user: User, movie: Movie
) -> None:
    order = await save_order(db_session, user, movie)

    response = await client.post(
        WEBHOOK_URL, content=json.dumps(checkout_event(COMPLETED, order.id))
    )

    assert response.status_code == 400
    assert response.json() == INVALID_SIGNATURE
    assert await stored_payments(db_session) == []


async def test_webhook_wrong_secret_returns_400(
    client: AsyncClient, db_session: AsyncSession, user: User, movie: Movie
) -> None:
    order = await save_order(db_session, user, movie)
    payload = json.dumps(checkout_event(COMPLETED, order.id)).encode()

    response = await client.post(
        WEBHOOK_URL,
        content=payload,
        headers={"Stripe-Signature": sign(payload, secret="whsec_forged")},
    )

    assert response.status_code == 400
    assert response.json() == INVALID_SIGNATURE
    assert (await stored_order(db_session, order.id)).status == OrderStatusEnum.PENDING


async def test_webhook_tampered_body_returns_400(
    client: AsyncClient, db_session: AsyncSession, user: User, movie: Movie
) -> None:
    """The signature belongs to another body (e.g. amount changed in transit)."""
    order = await save_order(db_session, user, movie)
    original = json.dumps(checkout_event(COMPLETED, order.id)).encode()
    tampered = json.dumps(checkout_event(COMPLETED, order.id, amount_total=1)).encode()

    response = await client.post(
        WEBHOOK_URL, content=tampered, headers={"Stripe-Signature": sign(original)}
    )

    assert response.status_code == 400
    assert await stored_payments(db_session) == []


async def test_webhook_old_timestamp_returns_400(
    client: AsyncClient, db_session: AsyncSession, user: User, movie: Movie
) -> None:
    """A correctly signed but replayed event (older than 5 minutes)."""
    order = await save_order(db_session, user, movie)
    payload = json.dumps(checkout_event(COMPLETED, order.id)).encode()
    old = int(time.time()) - 10 * 60

    response = await client.post(
        WEBHOOK_URL,
        content=payload,
        headers={"Stripe-Signature": sign(payload, timestamp=old)},
    )

    assert response.status_code == 400
    assert await stored_payments(db_session) == []


@pytest.mark.parametrize("header", ["", "garbage", "t=123"])
async def test_webhook_malformed_signature_returns_400(
    client: AsyncClient, header: str
) -> None:
    response = await client.post(
        WEBHOOK_URL, content=b"{}", headers={"Stripe-Signature": header}
    )

    assert response.status_code == 400
    assert response.json() == INVALID_SIGNATURE


async def test_webhook_signed_invalid_json_returns_400(client: AsyncClient) -> None:
    payload = b"not json"

    response = await client.post(
        WEBHOOK_URL, content=payload, headers={"Stripe-Signature": sign(payload)}
    )

    assert response.status_code == 400
    assert response.json() == INVALID_SIGNATURE


# --- ignored events ---


async def test_webhook_ignores_other_event_types(
    client: AsyncClient, db_session: AsyncSession, user: User, movie: Movie
) -> None:
    order = await save_order(db_session, user, movie)

    response = await send_event(
        client, checkout_event("payment_intent.succeeded", order.id)
    )

    assert response.status_code == 200
    assert await stored_payments(db_session) == []
    assert (await stored_order(db_session, order.id)).status == OrderStatusEnum.PENDING


async def test_webhook_ignores_session_without_order_id(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """E.g. `stripe trigger` or another app's session in the same sandbox."""
    event = checkout_event(COMPLETED, 1)
    event["data"]["object"]["metadata"] = {}

    response = await send_event(client, event)

    assert response.status_code == 200
    assert await stored_payments(db_session) == []


async def test_webhook_ignores_unpaid_completed_session(
    client: AsyncClient, db_session: AsyncSession, user: User, movie: Movie
) -> None:
    """Delayed payment methods complete the session before the money arrives."""
    order = await save_order(db_session, user, movie)

    response = await send_event(
        client, checkout_event(COMPLETED, order.id, payment_status="unpaid")
    )

    assert response.status_code == 200
    assert await stored_payments(db_session) == []
    assert (await stored_order(db_session, order.id)).status == OrderStatusEnum.PENDING
    assert await stored_purchased_ids(db_session, user) == set()


# --- checkout.session.completed ---


async def test_webhook_completed_marks_order_paid(
    client: AsyncClient,
    db_session: AsyncSession,
    user: User,
    movie: Movie,
    other_movie: Movie,
) -> None:
    order = await save_order(db_session, user, movie, other_movie)

    response = await send_event(
        client, checkout_event(COMPLETED, order.id, amount_total=1798)
    )

    assert response.status_code == 200
    assert (await stored_order(db_session, order.id)).status == OrderStatusEnum.PAID
    [payment] = await stored_payments(db_session)
    assert payment.user_id == user.id
    assert payment.order_id == order.id
    assert payment.status == PaymentStatusEnum.SUCCESSFUL
    assert payment.amount == Decimal("17.98")
    assert payment.external_payment_id == SESSION_ID
    assert await stored_purchased_ids(db_session, user) == {movie.id, other_movie.id}


async def test_webhook_completed_grants_only_this_order_movies(
    client: AsyncClient,
    db_session: AsyncSession,
    user: User,
    movie: Movie,
    other_movie: Movie,
) -> None:
    order = await save_order(db_session, user, movie)
    other_order = await save_order(db_session, user, other_movie)

    await send_event(client, checkout_event(COMPLETED, order.id))

    assert await stored_purchased_ids(db_session, user) == {movie.id}
    assert (
        await stored_order(db_session, other_order.id)
    ).status == OrderStatusEnum.PENDING


async def test_webhook_completed_twice_is_processed_once(
    client: AsyncClient, db_session: AsyncSession, user: User, movie: Movie
) -> None:
    """Stripe may deliver the same event again."""
    order = await save_order(db_session, user, movie)
    event = checkout_event(COMPLETED, order.id)

    await send_event(client, event)
    response = await send_event(client, event)

    assert response.status_code == 200
    assert len(await stored_payments(db_session)) == 1
    assert await stored_purchased_ids(db_session, user) == {movie.id}


async def test_webhook_completed_with_already_purchased_movie(
    client: AsyncClient,
    db_session: AsyncSession,
    user: User,
    movie: Movie,
    other_movie: Movie,
) -> None:
    """The movie was bought via another order while this one was being paid."""
    order = await save_order(db_session, user, movie, other_movie)
    await purchase(db_session, user, movie)

    response = await send_event(client, checkout_event(COMPLETED, order.id))

    assert response.status_code == 200
    assert (await stored_order(db_session, order.id)).status == OrderStatusEnum.PAID
    assert await stored_purchased_ids(db_session, user) == {movie.id, other_movie.id}


@pytest.mark.parametrize("status", [OrderStatusEnum.PAID, OrderStatusEnum.CANCELED])
async def test_webhook_completed_for_not_pending_order_still_grants_movies(
    client: AsyncClient,
    db_session: AsyncSession,
    caplog: pytest.LogCaptureFixture,
    user: User,
    movie: Movie,
    status: OrderStatusEnum,
) -> None:
    """Paid in two tabs / canceled meanwhile: the money arrived anyway."""
    order = await save_order(db_session, user, movie, status=status)

    with caplog.at_level(logging.WARNING, logger="src.payments.service"):
        response = await send_event(client, checkout_event(COMPLETED, order.id))

    assert response.status_code == 200
    assert (await stored_order(db_session, order.id)).status == OrderStatusEnum.PAID
    [payment] = await stored_payments(db_session)
    assert payment.status == PaymentStatusEnum.SUCCESSFUL
    assert await stored_purchased_ids(db_session, user) == {movie.id}
    assert "refund manually" in caplog.text


async def test_webhook_completed_second_session_records_second_payment(
    client: AsyncClient,
    db_session: AsyncSession,
    caplog: pytest.LogCaptureFixture,
    user: User,
    movie: Movie,
) -> None:
    """Two checkout sessions of one order both paid: two payments, one warning."""
    order = await save_order(db_session, user, movie)

    with caplog.at_level(logging.WARNING, logger="src.payments.service"):
        await send_event(client, checkout_event(COMPLETED, order.id))
        await send_event(
            client, checkout_event(COMPLETED, order.id, session_id="cs_test_456")
        )

    payments = await stored_payments(db_session)
    assert [p.external_payment_id for p in payments] == [SESSION_ID, "cs_test_456"]
    assert "refund manually" in caplog.text


async def test_webhook_completed_for_missing_order_logs_error(
    client: AsyncClient,
    db_session: AsyncSession,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The order was deleted (abandoned pending cleanup) before the payment."""
    with caplog.at_level(logging.ERROR, logger="src.payments.service"):
        response = await send_event(client, checkout_event(COMPLETED, UNKNOWN_ID))

    assert response.status_code == 200
    assert await stored_payments(db_session) == []
    assert "refund manually" in caplog.text


# --- checkout.session.expired ---


async def test_webhook_expired_records_canceled_payment(
    client: AsyncClient, db_session: AsyncSession, user: User, movie: Movie
) -> None:
    order = await save_order(db_session, user, movie)

    response = await send_event(client, checkout_event(EXPIRED, order.id))

    assert response.status_code == 200
    [payment] = await stored_payments(db_session)
    assert payment.order_id == order.id
    assert payment.status == PaymentStatusEnum.CANCELED
    assert payment.amount == Decimal("7.99")
    assert payment.external_payment_id == SESSION_ID
    # the user can try again
    assert (await stored_order(db_session, order.id)).status == OrderStatusEnum.PENDING
    assert await stored_purchased_ids(db_session, user) == set()


async def test_webhook_expired_twice_is_processed_once(
    client: AsyncClient, db_session: AsyncSession, user: User, movie: Movie
) -> None:
    order = await save_order(db_session, user, movie)
    event = checkout_event(EXPIRED, order.id)

    await send_event(client, event)
    response = await send_event(client, event)

    assert response.status_code == 200
    assert len(await stored_payments(db_session)) == 1


async def test_webhook_expired_then_new_session_paid(
    client: AsyncClient, db_session: AsyncSession, user: User, movie: Movie
) -> None:
    order = await save_order(db_session, user, movie)

    await send_event(client, checkout_event(EXPIRED, order.id))
    await send_event(
        client, checkout_event(COMPLETED, order.id, session_id="cs_test_456")
    )

    payments = await stored_payments(db_session)
    assert [p.status for p in payments] == [
        PaymentStatusEnum.CANCELED,
        PaymentStatusEnum.SUCCESSFUL,
    ]
    assert (await stored_order(db_session, order.id)).status == OrderStatusEnum.PAID
    assert await stored_purchased_ids(db_session, user) == {movie.id}


async def test_webhook_expired_for_missing_order_is_ignored(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    response = await send_event(client, checkout_event(EXPIRED, UNKNOWN_ID))

    assert response.status_code == 200
    assert await stored_payments(db_session) == []


# --- confirmation email ---


async def test_webhook_completed_sends_confirmation_email(
    client: AsyncClient,
    db_session: AsyncSession,
    send_payment_confirmation_email_mock: MagicMock,
    user: User,
    movie: Movie,
    other_movie: Movie,
) -> None:
    """Amount is the one Stripe charged, as a string (Decimal is not JSON)."""
    order = await save_order(db_session, user, movie, other_movie)

    await send_event(client, checkout_event(COMPLETED, order.id, amount_total=1798))

    send_payment_confirmation_email_mock.delay.assert_called_once_with(
        user.email, order.id, "17.98"
    )


async def test_webhook_completed_twice_sends_one_email(
    client: AsyncClient,
    db_session: AsyncSession,
    send_payment_confirmation_email_mock: MagicMock,
    user: User,
    movie: Movie,
) -> None:
    order = await save_order(db_session, user, movie)
    event = checkout_event(COMPLETED, order.id)

    await send_event(client, event)
    await send_event(client, event)

    send_payment_confirmation_email_mock.delay.assert_called_once()


async def test_webhook_completed_for_canceled_order_sends_email(
    client: AsyncClient,
    db_session: AsyncSession,
    send_payment_confirmation_email_mock: MagicMock,
    user: User,
    movie: Movie,
) -> None:
    """The money arrived and the movies are granted, so the user is notified."""
    order = await save_order(db_session, user, movie, status=OrderStatusEnum.CANCELED)

    await send_event(client, checkout_event(COMPLETED, order.id))

    send_payment_confirmation_email_mock.delay.assert_called_once_with(
        user.email, order.id, "7.99"
    )


@pytest.mark.parametrize(
    ("event_type", "payment_status"),
    [(EXPIRED, "unpaid"), (COMPLETED, "unpaid")],
    ids=["expired", "completed_unpaid"],
)
async def test_webhook_without_payment_sends_no_email(
    client: AsyncClient,
    db_session: AsyncSession,
    send_payment_confirmation_email_mock: MagicMock,
    user: User,
    movie: Movie,
    event_type: str,
    payment_status: str,
) -> None:
    order = await save_order(db_session, user, movie)

    await send_event(
        client, checkout_event(event_type, order.id, payment_status=payment_status)
    )

    send_payment_confirmation_email_mock.delay.assert_not_called()


async def test_webhook_completed_for_missing_order_sends_no_email(
    client: AsyncClient, send_payment_confirmation_email_mock: MagicMock
) -> None:
    await send_event(client, checkout_event(COMPLETED, UNKNOWN_ID))

    send_payment_confirmation_email_mock.delay.assert_not_called()


async def test_webhook_invalid_signature_sends_no_email(
    client: AsyncClient,
    db_session: AsyncSession,
    send_payment_confirmation_email_mock: MagicMock,
    user: User,
    movie: Movie,
) -> None:
    order = await save_order(db_session, user, movie)
    payload = json.dumps(checkout_event(COMPLETED, order.id)).encode()

    await client.post(
        WEBHOOK_URL,
        content=payload,
        headers={"Stripe-Signature": sign(payload, secret="whsec_forged")},
    )

    send_payment_confirmation_email_mock.delay.assert_not_called()
