"""seed user groups

Revision ID: e134395c8db0
Revises: 6752baf392c3
Create Date: 2026-10-28 23:16:19.391130

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e134395c8db0"
down_revision: Union[str, Sequence[str], None] = "6752baf392c3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

user_groups = sa.table("user_groups", sa.column("name", sa.String))

GROUPS = ["user", "moderator", "admin"]


def upgrade() -> None:
    op.bulk_insert(user_groups, [{"name": name} for name in GROUPS])


def downgrade() -> None:
    op.execute(user_groups.delete().where(user_groups.c.name.in_(GROUPS)))
