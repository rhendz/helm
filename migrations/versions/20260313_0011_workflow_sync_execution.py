"""extend workflow sync records with execution attempt metadata

Revision ID: 20260313_0011
Revises: 20260313_0010
Create Date: 2026-03-13 00:11:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260313_0011"
down_revision: str | None = "20260313_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "workflow_sync_records",
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "workflow_sync_records",
        sa.Column("last_attempt_step_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_workflow_sync_records_last_attempt_step_id",
        "workflow_sync_records",
        "workflow_steps",
        ["last_attempt_step_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.alter_column("workflow_sync_records", "attempt_count", server_default=None)


def downgrade() -> None:
    op.drop_constraint(
        "fk_workflow_sync_records_last_attempt_step_id",
        "workflow_sync_records",
        type_="foreignkey",
    )
    op.drop_column("workflow_sync_records", "last_attempt_step_id")
    op.drop_column("workflow_sync_records", "attempt_count")
