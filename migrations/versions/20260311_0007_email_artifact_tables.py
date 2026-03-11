"""email artifact tables

Revision ID: 20260311_0007
Revises: 20260310_0006
Create Date: 2026-03-11 09:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260311_0007"
down_revision: str | None = "20260310_0006"
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
        "classification_artifacts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("internal_uuid", sa.String(length=36), nullable=False),
        sa.Column("email_thread_id", sa.Integer(), nullable=False),
        sa.Column("email_message_id", sa.Integer(), nullable=False),
        sa.Column("classification", sa.String(length=64), nullable=False),
        sa.Column("priority_score", sa.Integer(), nullable=False),
        sa.Column("business_state", sa.String(length=32), nullable=False),
        sa.Column("visible_labels", sa.JSON(), nullable=False),
        sa.Column("action_reason", sa.String(length=32), nullable=True),
        sa.Column("resurfacing_source", sa.String(length=32), nullable=True),
        sa.Column("confidence_band", sa.String(length=16), nullable=True),
        sa.Column("decision_context", sa.JSON(), nullable=False),
        sa.Column("model_name", sa.String(length=128), nullable=True),
        sa.Column("prompt_version", sa.String(length=64), nullable=True),
        _timestamp_column("created_at"),
        sa.ForeignKeyConstraint(["email_message_id"], ["email_messages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["email_thread_id"], ["email_threads.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("internal_uuid"),
    )
    op.create_index(
        "ix_classification_artifacts_thread_id_id",
        "classification_artifacts",
        ["email_thread_id", "id"],
        unique=False,
    )
    op.create_index(
        "ix_classification_artifacts_message_id_id",
        "classification_artifacts",
        ["email_message_id", "id"],
        unique=False,
    )

    op.create_table(
        "draft_reasoning_artifacts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("internal_uuid", sa.String(length=36), nullable=False),
        sa.Column("email_draft_id", sa.Integer(), nullable=False),
        sa.Column("email_thread_id", sa.Integer(), nullable=False),
        sa.Column("action_proposal_id", sa.Integer(), nullable=True),
        sa.Column("schema_version", sa.String(length=32), nullable=False),
        sa.Column("prompt_context", sa.JSON(), nullable=False),
        sa.Column("model_metadata", sa.JSON(), nullable=False),
        sa.Column("reasoning_payload", sa.JSON(), nullable=False),
        sa.Column("refinement_metadata", sa.JSON(), nullable=False),
        _timestamp_column("created_at"),
        sa.ForeignKeyConstraint(
            ["action_proposal_id"],
            ["action_proposals.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(["email_draft_id"], ["email_drafts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["email_thread_id"], ["email_threads.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("internal_uuid"),
    )
    op.create_index(
        "ix_draft_reasoning_artifacts_draft_id_id",
        "draft_reasoning_artifacts",
        ["email_draft_id", "id"],
        unique=False,
    )
    op.create_index(
        "ix_draft_reasoning_artifacts_thread_id_id",
        "draft_reasoning_artifacts",
        ["email_thread_id", "id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_draft_reasoning_artifacts_thread_id_id",
        table_name="draft_reasoning_artifacts",
    )
    op.drop_index(
        "ix_draft_reasoning_artifacts_draft_id_id",
        table_name="draft_reasoning_artifacts",
    )
    op.drop_table("draft_reasoning_artifacts")
    op.drop_index(
        "ix_classification_artifacts_message_id_id",
        table_name="classification_artifacts",
    )
    op.drop_index(
        "ix_classification_artifacts_thread_id_id",
        table_name="classification_artifacts",
    )
    op.drop_table("classification_artifacts")
