import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from src.config.settings import Settings

TEMPLATES_DIR = Path(__file__).parent / "templates"
SMTP_TIMEOUT_SECONDS = 10

_jinja_env = Environment(
    loader=FileSystemLoader(TEMPLATES_DIR),
    autoescape=select_autoescape(["html"]),
)


def render_template(template_name: str, **context: object) -> str:
    """Render an email template from TEMPLATES_DIR (HTML is autoescaped)."""
    template = _jinja_env.get_template(template_name)
    return template.render(**context)


def send_email(to: str, subject: str, html_body: str, settings: Settings) -> None:
    """Send an HTML email over SMTP (sync, with a timeout).

    STARTTLS and login are used only when SMTP_USE_TLS / SMTP_USER are set
    (Mailpit in dev needs neither). Network errors raise OSError, which the
    Celery tasks retry.
    """
    message = EmailMessage()
    message["From"] = settings.EMAIL_FROM
    message["To"] = to
    message["Subject"] = subject
    message.set_content(html_body, subtype="html")

    with smtplib.SMTP(
        settings.SMTP_HOST, settings.SMTP_PORT, timeout=SMTP_TIMEOUT_SECONDS
    ) as smtp:
        if settings.SMTP_USE_TLS:
            smtp.starttls(context=ssl.create_default_context())
        if settings.SMTP_USER:
            smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD.get_secret_value())
        smtp.send_message(message)
