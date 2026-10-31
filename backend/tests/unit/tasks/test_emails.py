from unittest.mock import MagicMock

import pytest

from src.config.settings import get_settings
from src.tasks.emails import send_activation_email


def test_send_activation_email_sends_link_with_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    send_email_mock = MagicMock()
    monkeypatch.setattr("src.tasks.emails.send_email", send_email_mock)

    # Calling the task directly runs it synchronously, without a broker.
    send_activation_email("user@example.com", "raw-token")

    send_email_mock.assert_called_once()
    to, subject, html_body, _ = send_email_mock.call_args.args
    assert to == "user@example.com"
    assert subject == "Activate your account"
    assert f"{get_settings().FRONTEND_URL}/activate?token=raw-token" in html_body
