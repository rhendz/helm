"""multi-user identity foundation — schema wipe + recreate

Revision ID: 20260318_0014
Revises: 20260317_0013
Create Date: 2026-03-18
"""

from collections.abc import Sequence

from alembic import op
from helm_storage import models  # noqa: F401
from helm_storage.db import Base

# revision identifiers, used by Alembic.
revision: str = "20260318_0014"
down_revision: str = "20260317_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
    Base.metadata.create_all(bind=bind)
