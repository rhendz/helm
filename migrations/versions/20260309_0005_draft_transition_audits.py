"""add draft transition audits table

Revision ID: 20260309_0005
Revises: 20260309_0004
Create Date: 2026-03-09 20:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260309_0005"
down_revision: str | None = "20260309_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "draft_transition_audits",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("draft_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("from_status", sa.String(length=32), nullable=True),
        sa.Column("to_status", sa.String(length=32), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("reason", sa.String(length=128), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_draft_transition_audits_draft_id",
        "draft_transition_audits",
        ["draft_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_draft_transition_audits_draft_id", table_name="draft_transition_audits")
    op.drop_table("draft_transition_audits")

