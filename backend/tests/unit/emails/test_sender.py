from unittest.mock import MagicMock

import pytest
from pydantic import SecretStr

from src.config.settings import Settings, get_settings
from src.emails.sender import render_template, send_email


@pytest.fixture
def smtp_mock(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Replace `smtplib.SMTP`; returns the class mock (its calls = constructor)."""
    smtp_class_mock = MagicMock()
    monkeypatch.setattr("src.emails.sender.smtplib.SMTP", smtp_class_mock)
    return smtp_class_mock


@pytest.fixture
def smtp_settings() -> Settings:
    return get_settings().model_copy(
        update={
            "SMTP_HOST": "smtp.test",
            "SMTP_PORT": 2525,
            "SMTP_USER": "",
            "SMTP_USE_TLS": False,
            "EMAIL_FROM": "noreply@test.local",
        }
    )


def connection(smtp_mock: MagicMock) -> MagicMock:
    """The object bound by `with smtplib.SMTP(...) as smtp`."""
    result: MagicMock = smtp_mock.return_value.__enter__.return_value
    return result


def test_render_template_inserts_context() -> None:
    html = render_template(
        "activation.html",
        activation_link="http://front.test/activate?token=abc",
        expire_hours=24,
    )

    assert 'href="http://front.test/activate?token=abc"' in html
    assert "24 hours" in html


def test_render_template_escapes_html() -> None:
    html = render_template(
        "activation.html", activation_link="<script>", expire_hours=24
    )

    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_send_email_builds_html_message(
    smtp_mock: MagicMock, smtp_settings: Settings
) -> None:
    send_email("user@example.com", "Subject", "<p>Hi</p>", smtp_settings)

    smtp_mock.assert_called_once_with("smtp.test", 2525, timeout=10)
    connection(smtp_mock).send_message.assert_called_once()
    message = connection(smtp_mock).send_message.call_args.args[0]
    assert message["From"] == "noreply@test.local"
    assert message["To"] == "user@example.com"
    assert message["Subject"] == "Subject"
    assert message.get_content_type() == "text/html"


def test_send_email_skips_tls_and_login_by_default(
    smtp_mock: MagicMock, smtp_settings: Settings
) -> None:
    send_email("user@example.com", "Subject", "<p>Hi</p>", smtp_settings)

    connection(smtp_mock).starttls.assert_not_called()
    connection(smtp_mock).login.assert_not_called()


def test_send_email_uses_tls_and_login_when_configured(
    smtp_mock: MagicMock, smtp_settings: Settings
) -> None:
    settings = smtp_settings.model_copy(
        update={
            "SMTP_USE_TLS": True,
            "SMTP_USER": "user",
            "SMTP_PASSWORD": SecretStr("secret"),
        }
    )

    send_email("user@example.com", "Subject", "<p>Hi</p>", settings)

    connection(smtp_mock).starttls.assert_called_once()
    connection(smtp_mock).login.assert_called_once_with("user", "secret")
