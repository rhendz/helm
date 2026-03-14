"""add workflow sync records

Revision ID: 20260313_0010
Revises: 20260313_0009
Create Date: 2026-03-13 00:10:00.000000
"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "20260313_0010"
down_revision: str | None = "20260313_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # All workflow tables are already created by the baseline migration (0001)
    # via Base.metadata.create_all(). This migration is a no-op.
    pass


def downgrade() -> None:
    # This migration is a no-op as tables are managed by the baseline migration.
    pass
