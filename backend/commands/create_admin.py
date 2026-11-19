"""Create the first admin (or make an existing user an admin).

Run from the repo root:
    docker compose exec web python -m commands.create_admin admin@example.com

A new user: asks for a password (same rules as registration) and creates
an active admin. An existing user: becomes an active admin, password unchanged.
"""

import argparse
import sys
from getpass import getpass

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.accounts.models import User, UserGroup, UserGroupEnum
from src.accounts.schemas import UserRegisterRequest
from src.accounts.security import hash_password
from src.database.sync_session import SyncSessionLocal
from src.movies import models as _movies_models  # noqa: F401 (User relationships)


def ask_password() -> str:
    """Ask for the password twice; exit if the two inputs differ."""
    password = getpass("Password: ")
    if password != getpass("Password again: "):
        sys.exit("Passwords do not match.")
    return password


def validate(email: str, password: str) -> UserRegisterRequest:
    """Check email and password with the registration schema; exit on errors."""
    try:
        return UserRegisterRequest(email=email, password=password)
    except ValidationError as exc:
        errors = exc.errors()
        sys.exit("\n".join(e["msg"].removeprefix("Value error, ") for e in errors))


def create_admin(session: Session, email: str) -> str:
    """Promote the user with this email or create a new admin; return a summary."""
    admin_group = session.scalars(
        select(UserGroup).where(UserGroup.name == UserGroupEnum.ADMIN)
    ).one()
    # Email is normalized by the schema; a dummy password just passes validation.
    email = validate(email, "Placeholder1!").email

    user = session.scalars(select(User).where(User.email == email)).first()
    if user is not None:
        user.group = admin_group
        user.is_active = True
        user.activation_token = None  # delete-orphan removes the unused token
        session.commit()
        return f"{email} is now an admin."

    data = validate(email, ask_password())
    session.add(
        User(
            email=data.email,
            hashed_password=hash_password(data.password),
            group=admin_group,
            is_active=True,
        )
    )
    session.commit()
    return f"Admin {email} created."


def main() -> None:
    parser = argparse.ArgumentParser(description="Create or promote an admin.")
    parser.add_argument("email")
    args = parser.parse_args()
    with SyncSessionLocal() as session:
        print(create_admin(session, args.email))


if __name__ == "__main__":
    main()
