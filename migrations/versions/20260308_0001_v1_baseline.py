"""current schema baseline

Revision ID: 20260308_0001
Revises:
Create Date: 2026-03-08 23:35:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from helm_storage import models  # noqa: F401
from helm_storage.db import Base

# revision identifiers, used by Alembic.
revision: str = "20260308_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamp_column(name: str) -> sa.Column:
    return sa.Column(
        name,
        sa.DateTime(timezone=True),
        server_default=sa.text("CURRENT_TIMESTAMP"),
        nullable=False,
    )


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
