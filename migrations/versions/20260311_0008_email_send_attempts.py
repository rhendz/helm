"""email send attempts

Revision ID: 20260311_0008
Revises: 20260311_0007
Create Date: 2026-03-11 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260311_0008"
down_revision: str | None = "20260311_0007"
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
    op.create_table(
        "email_send_attempts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("internal_uuid", sa.String(length=36), nullable=False),
        sa.Column("draft_id", sa.Integer(), nullable=False),
        sa.Column("email_thread_id", sa.Integer(), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("failure_class", sa.String(length=64), nullable=True),
        sa.Column("failure_message", sa.Text(), nullable=True),
        sa.Column("provider_error_code", sa.String(length=64), nullable=True),
        sa.Column("provider_message_id", sa.String(length=255), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        _timestamp_column("created_at"),
        _timestamp_column("updated_at"),
        sa.ForeignKeyConstraint(["draft_id"], ["email_drafts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["email_thread_id"], ["email_threads.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("internal_uuid"),
    )
    op.create_index(
        "ix_email_send_attempts_draft_id_id",
        "email_send_attempts",
        ["draft_id", "id"],
        unique=False,
    )
    op.create_index(
        "ix_email_send_attempts_draft_id_status",
        "email_send_attempts",
        ["draft_id", "status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_email_send_attempts_draft_id_status", table_name="email_send_attempts")
    op.drop_index("ix_email_send_attempts_draft_id_id", table_name="email_send_attempts")
    op.drop_table("email_send_attempts")
