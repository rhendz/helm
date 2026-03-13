"""add workflow approval checkpoints

Revision ID: 20260313_0009
Revises: 20260313_0008
Create Date: 2026-03-13 00:09:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260313_0009"
down_revision: str | None = "20260313_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("workflow_runs", sa.Column("blocked_reason", sa.String(length=64), nullable=True))
    op.add_column("workflow_runs", sa.Column("resume_step_name", sa.String(length=128), nullable=True))
    op.add_column("workflow_runs", sa.Column("resume_step_attempt", sa.Integer(), nullable=True))

    op.create_table(
        "workflow_approval_checkpoints",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("step_id", sa.Integer(), nullable=False),
        sa.Column("target_artifact_id", sa.Integer(), nullable=False),
        sa.Column("resume_step_name", sa.String(length=128), nullable=False),
        sa.Column("resume_step_attempt", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("allowed_actions", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("decision", sa.String(length=32), nullable=True),
        sa.Column("decision_actor", sa.String(length=255), nullable=True),
        sa.Column("decision_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revision_feedback", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["run_id"], ["workflow_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["step_id"], ["workflow_steps.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["target_artifact_id"], ["workflow_artifacts.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("workflow_approval_checkpoints")
    op.drop_column("workflow_runs", "resume_step_attempt")
    op.drop_column("workflow_runs", "resume_step_name")
    op.drop_column("workflow_runs", "blocked_reason")
