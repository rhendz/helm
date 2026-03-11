"""email deep seed queue

Revision ID: 20260311_0010
Revises: 20260311_0009
Create Date: 2026-03-11 13:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260311_0010"
down_revision: str | None = "20260311_0009"
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
        "email_deep_seed_queue",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("internal_uuid", sa.String(length=36), nullable=False),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("provider_thread_id", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("seed_reason", sa.String(length=64), nullable=False),
        sa.Column("message_count", sa.Integer(), nullable=False),
        sa.Column("latest_received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sample_subject", sa.String(length=512), nullable=False),
        sa.Column("from_addresses", sa.JSON(), nullable=False),
        sa.Column("thread_payload", sa.JSON(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("email_thread_id", sa.Integer(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        _timestamp_column("created_at"),
        _timestamp_column("updated_at"),
        sa.ForeignKeyConstraint(["email_thread_id"], ["email_threads.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("internal_uuid"),
    )
    op.create_index(
        "ix_email_deep_seed_queue_status_id",
        "email_deep_seed_queue",
        ["status", "id"],
        unique=False,
    )
    op.create_index(
        "ix_email_deep_seed_queue_source_thread_status",
        "email_deep_seed_queue",
        ["source_type", "provider_thread_id", "status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_email_deep_seed_queue_source_thread_status",
        table_name="email_deep_seed_queue",
    )
    op.drop_index(
        "ix_email_deep_seed_queue_status_id",
        table_name="email_deep_seed_queue",
    )
    op.drop_table("email_deep_seed_queue")
