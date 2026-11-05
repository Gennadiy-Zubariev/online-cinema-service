#!/usr/bin/env bash
# Applies all migrations, rolls back the last one and re-applies it
# to verify that its downgrade() works.
set -euo pipefail

cd "$(dirname "$0")/.."

poetry run alembic upgrade head
poetry run alembic downgrade -1
poetry run alembic upgrade head
