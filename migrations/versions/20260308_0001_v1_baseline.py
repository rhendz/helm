"""v1 baseline schema

Revision ID: 20260308_0001
Revises:
Create Date: 2026-03-08 23:35:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

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
    op.create_table(
        "contacts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("linkedin_url", sa.String(length=512), nullable=True),
        sa.Column("telegram_handle", sa.String(length=255), nullable=True),
        sa.Column("company", sa.String(length=255), nullable=True),
        sa.Column("relationship_type", sa.String(length=64), nullable=True),
        sa.Column("importance_score", sa.Integer(), nullable=False, server_default="3"),
        _timestamp_column("created_at"),
        _timestamp_column("updated_at"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )

    op.create_table(
        "action_items",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("source_id", sa.String(length=255), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="open"),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        _timestamp_column("created_at"),
        _timestamp_column("updated_at"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_action_items_status_priority",
        "action_items",
        ["status", "priority"],
        unique=False,
    )

    op.create_table(
        "agent_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("agent_name", sa.String(length=64), nullable=False),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("source_id", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        _timestamp_column("started_at"),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "draft_replies",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("channel_type", sa.String(length=32), nullable=False, server_default="email"),
        sa.Column("thread_id", sa.String(length=255), nullable=True),
        sa.Column("contact_id", sa.Integer(), nullable=True),
        sa.Column("draft_text", sa.Text(), nullable=False),
        sa.Column("tone", sa.String(length=32), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        _timestamp_column("created_at"),
        _timestamp_column("updated_at"),
        sa.ForeignKeyConstraint(["contact_id"], ["contacts.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_draft_replies_status_id",
        "draft_replies",
        ["status", "id"],
        unique=False,
    )

    op.create_table(
        "digest_items",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("domain", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("related_contact_id", sa.Integer(), nullable=True),
        sa.Column("related_action_id", sa.Integer(), nullable=True),
        _timestamp_column("created_at"),
        sa.ForeignKeyConstraint(
            ["related_action_id"], ["action_items.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["related_contact_id"], ["contacts.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_digest_items_domain_priority",
        "digest_items",
        ["domain", "priority"],
        unique=False,
    )

    op.create_table(
        "email_messages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("provider_message_id", sa.String(length=255), nullable=False),
        sa.Column("thread_id", sa.String(length=255), nullable=False),
        sa.Column("from_address", sa.String(length=320), nullable=False),
        sa.Column("subject", sa.String(length=512), nullable=False),
        sa.Column("body_text", sa.Text(), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider_message_id"),
    )

    op.create_table(
        "email_threads",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("latest_subject", sa.String(length=512), nullable=False),
        sa.Column("thread_summary", sa.Text(), nullable=True),
        sa.Column("category", sa.String(length=64), nullable=True),
        sa.Column("priority_score", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="open"),
        sa.PrimaryKeyConstraint("id"),
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

    op.create_table(
        "linkedin_threads",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("thread_summary", sa.Text(), nullable=True),
        sa.Column("category", sa.String(length=64), nullable=True),
        sa.Column("priority_score", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="open"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "opportunities",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("contact_id", sa.Integer(), nullable=True),
        sa.Column("company", sa.String(length=255), nullable=False),
        sa.Column("role_title", sa.String(length=255), nullable=False),
        sa.Column("channel_source", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="open"),
        sa.Column("priority_score", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("notes", sa.Text(), nullable=True),
        _timestamp_column("created_at"),
        _timestamp_column("updated_at"),
        sa.ForeignKeyConstraint(["contact_id"], ["contacts.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "study_sessions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        _timestamp_column("created_at"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "knowledge_gaps",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("topic", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("severity", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("source_session_id", sa.Integer(), nullable=True),
        _timestamp_column("created_at"),
        _timestamp_column("updated_at"),
        sa.ForeignKeyConstraint(["source_session_id"], ["study_sessions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "learning_tasks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="open"),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("related_gap_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["related_gap_id"], ["knowledge_gaps.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("learning_tasks")
    op.drop_table("knowledge_gaps")
    op.drop_table("study_sessions")
    op.drop_table("opportunities")
    op.drop_table("linkedin_threads")
    op.drop_table("linkedin_messages")
    op.drop_table("email_threads")
    op.drop_table("email_messages")
    op.drop_index("ix_digest_items_domain_priority", table_name="digest_items")
    op.drop_table("digest_items")
    op.drop_index("ix_draft_replies_status_id", table_name="draft_replies")
    op.drop_table("draft_replies")
    op.drop_table("agent_runs")
    op.drop_index("ix_action_items_status_priority", table_name="action_items")
    op.drop_table("action_items")
    op.drop_table("contacts")
