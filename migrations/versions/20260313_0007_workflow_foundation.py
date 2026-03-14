"""add workflow foundation tables

Revision ID: 20260313_0007
Revises: 20260310_0006
Create Date: 2026-03-13 00:07:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260313_0007"
down_revision: str | None = "20260310_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "workflow_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("internal_uuid", sa.String(length=36), nullable=False),
        sa.Column("workflow_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("current_step_name", sa.String(length=128), nullable=True),
        sa.Column("needs_action", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("current_step_attempt", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("validation_outcome_summary", sa.Text(), nullable=True),
        sa.Column("execution_error_summary", sa.Text(), nullable=True),
        sa.Column("failure_class", sa.String(length=64), nullable=True),
        sa.Column("retry_state", sa.String(length=32), nullable=True),
        sa.Column("last_event_summary", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("internal_uuid"),
    )
    op.create_table(
        "workflow_steps",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("step_name", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("attempt_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("validation_outcome_summary", sa.Text(), nullable=True),
        sa.Column("execution_error_summary", sa.Text(), nullable=True),
        sa.Column("failure_class", sa.String(length=64), nullable=True),
        sa.Column("retry_state", sa.String(length=32), nullable=True),
        sa.Column("retryable", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["run_id"], ["workflow_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "step_name", "attempt_number", name="uq_workflow_step_attempt"),
    )
    op.create_table(
        "workflow_artifacts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("step_id", sa.Integer(), nullable=True),
        sa.Column("artifact_type", sa.String(length=64), nullable=False),
        sa.Column("schema_version", sa.String(length=32), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("producer_step_name", sa.String(length=128), nullable=True),
        sa.Column("lineage_parent_id", sa.Integer(), nullable=True),
        sa.Column("supersedes_artifact_id", sa.Integer(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["lineage_parent_id"], ["workflow_artifacts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["run_id"], ["workflow_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["step_id"], ["workflow_steps.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["supersedes_artifact_id"], ["workflow_artifacts.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "artifact_type", "version_number", name="uq_workflow_artifact_version"),
    )
    op.create_table(
        "workflow_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("step_id", sa.Integer(), nullable=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("run_status", sa.String(length=32), nullable=True),
        sa.Column("step_status", sa.String(length=32), nullable=True),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["run_id"], ["workflow_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["step_id"], ["workflow_steps.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("workflow_events")
    op.drop_table("workflow_artifacts")
    op.drop_table("workflow_steps")
    op.drop_table("workflow_runs")
