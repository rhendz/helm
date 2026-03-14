"""add workflow sync records

Revision ID: 20260313_0010
Revises: 20260313_0009
Create Date: 2026-03-13 00:10:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260313_0010"
down_revision: str | None = "20260313_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "workflow_sync_records",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("step_id", sa.Integer(), nullable=False),
        sa.Column("proposal_artifact_id", sa.Integer(), nullable=False),
        sa.Column("proposal_version_number", sa.Integer(), nullable=False),
        sa.Column("target_system", sa.String(length=64), nullable=False),
        sa.Column("sync_kind", sa.String(length=64), nullable=False),
        sa.Column("planned_item_key", sa.String(length=255), nullable=False),
        sa.Column("execution_order", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("payload_fingerprint", sa.String(length=128), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("external_object_id", sa.String(length=255), nullable=True),
        sa.Column("last_error_summary", sa.Text(), nullable=True),
        sa.Column("last_attempted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("supersedes_sync_record_id", sa.Integer(), nullable=True),
        sa.Column("replayed_from_sync_record_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["proposal_artifact_id"], ["workflow_artifacts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["replayed_from_sync_record_id"], ["workflow_sync_records.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["run_id"], ["workflow_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["step_id"], ["workflow_steps.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["supersedes_sync_record_id"], ["workflow_sync_records.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "proposal_artifact_id",
            "proposal_version_number",
            "target_system",
            "sync_kind",
            "planned_item_key",
            name="uq_workflow_sync_record_identity",
        ),
        sa.UniqueConstraint("idempotency_key", name="uq_workflow_sync_record_idempotency"),
    )


def downgrade() -> None:
    op.drop_table("workflow_sync_records")
