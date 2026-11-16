"""Parameters sent to Stripe when a Checkout Session is created (no network)."""

from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock

import pytest

from src.config.settings import get_settings
from src.movies.models import Movie
from src.orders.models import OrderItem
from src.payments import stripe_client as stripe_module
from src.payments.stripe_client import create_checkout_session

SESSION_URL = "https://checkout.stripe.test/c/pay/cs_test_123"


@pytest.fixture
def stripe_mock(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Replace the module-level StripeClient; `create` returns a session."""
    client = MagicMock()
    client.v1.checkout.sessions.create.return_value.url = SESSION_URL
    monkeypatch.setattr(stripe_module, "stripe_client", client)
    return client


def item(name: str, price: str) -> OrderItem:
    return OrderItem(movie=Movie(name=name), price_at_order=Decimal(price))


def sent_params(stripe_mock: MagicMock) -> dict[str, Any]:
    stripe_mock.v1.checkout.sessions.create.assert_called_once()
    params: dict[str, Any] = stripe_mock.v1.checkout.sessions.create.call_args.kwargs[
        "params"
    ]
    return params


def test_create_checkout_session_returns_session_url(stripe_mock: MagicMock) -> None:
    assert create_checkout_session(42, [item("Inception", "7.99")]) == SESSION_URL


def test_create_checkout_session_sends_line_per_movie_in_cents(
    stripe_mock: MagicMock,
) -> None:
    create_checkout_session(42, [item("Inception", "7.99"), item("Dune", "19.99")])

    params = sent_params(stripe_mock)
    assert params["mode"] == "payment"
    assert params["line_items"] == [
        {
            "quantity": 1,
            "price_data": {
                "currency": "usd",
                "unit_amount": 799,
                "product_data": {"name": "Inception"},
            },
        },
        {
            "quantity": 1,
            "price_data": {
                "currency": "usd",
                "unit_amount": 1999,
                "product_data": {"name": "Dune"},
            },
        },
    ]


def test_create_checkout_session_sends_order_id_as_string(
    stripe_mock: MagicMock,
) -> None:
    """Stripe metadata values must be strings; the webhook reads them back."""
    create_checkout_session(42, [item("Inception", "7.99")])

    assert sent_params(stripe_mock)["metadata"] == {"order_id": "42"}


def test_create_checkout_session_sends_redirect_urls(stripe_mock: MagicMock) -> None:
    """`{CHECKOUT_SESSION_ID}` stays literal: Stripe substitutes it itself."""
    create_checkout_session(42, [item("Inception", "7.99")])

    params = sent_params(stripe_mock)
    frontend_url = get_settings().FRONTEND_URL
    assert params["success_url"] == (
        f"{frontend_url}/payment/success?session_id={{CHECKOUT_SESSION_ID}}"
    )
    assert params["cancel_url"] == f"{frontend_url}/payment/cancel"


def test_create_checkout_session_without_url_raises(stripe_mock: MagicMock) -> None:
    stripe_mock.v1.checkout.sessions.create.return_value.url = None

    with pytest.raises(RuntimeError):
        create_checkout_session(42, [item("Inception", "7.99")])
