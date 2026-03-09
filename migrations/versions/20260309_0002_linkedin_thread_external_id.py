"""add external thread id for linkedin thread upserts

Revision ID: 20260309_0002
Revises: 20260308_0001
Create Date: 2026-03-09 03:05:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260309_0002"
down_revision: str | None = "20260308_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "linkedin_threads",
        sa.Column("external_thread_id", sa.String(length=255), nullable=True),
    )
    op.create_unique_constraint(
        "uq_linkedin_threads_external_thread_id",
        "linkedin_threads",
        ["external_thread_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_linkedin_threads_external_thread_id",
        "linkedin_threads",
        type_="unique",
    )
    op.drop_column("linkedin_threads", "external_thread_id")
