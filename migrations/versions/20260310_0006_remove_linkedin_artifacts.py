"""remove linkedin artifacts from schema

Revision ID: 20260310_0006
Revises: 20260309_0005
Create Date: 2026-03-10 11:15:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260310_0006"
down_revision: str | None = "20260309_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_table("linkedin_messages")
    op.drop_table("linkedin_threads")
    op.drop_column("contacts", "linkedin_url")


def downgrade() -> None:
    op.add_column("contacts", sa.Column("linkedin_url", sa.String(length=512), nullable=True))
    op.create_table(
        "linkedin_threads",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("external_thread_id", sa.String(length=255), nullable=True),
        sa.Column("thread_summary", sa.Text(), nullable=True),
        sa.Column("category", sa.String(length=64), nullable=True),
        sa.Column("priority_score", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="open"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_thread_id", name="uq_linkedin_threads_external_thread_id"),
    )
    op.create_table(
        "linkedin_messages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("provider_message_id", sa.String(length=255), nullable=False),
        sa.Column("thread_id", sa.String(length=255), nullable=False),
        sa.Column("sender_name", sa.String(length=255), nullable=False),
        sa.Column("body_text", sa.Text(), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider_message_id"),
    )
