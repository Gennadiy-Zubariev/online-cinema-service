from src.config.settings import get_settings
from src.emails.sender import render_template, send_email
from src.tasks.celery_app import celery_app


@celery_app.task(autoretry_for=(OSError,), retry_backoff=True, max_retries=5)
def send_activation_email(email: str, token: str) -> None:
    settings = get_settings()
    activation_link = f"{settings.FRONTEND_URL}/activate?token={token}"
    html_body = render_template(
        "activation.html",
        activation_link=activation_link,
        expire_hours=settings.ACTIVATION_TOKEN_EXPIRE_HOURS,
    )
    send_email(email, "Activate your account", html_body, settings)
