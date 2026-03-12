"""add workflow sync recovery lineage metadata

Revision ID: 20260313_0012
Revises: 20260313_0011
Create Date: 2026-03-13 00:12:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260313_0012"
down_revision: str | None = "20260313_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("uq_workflow_sync_record_identity", "workflow_sync_records", type_="unique")
    op.add_column(
        "workflow_sync_records",
        sa.Column("lineage_generation", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "workflow_sync_records",
        sa.Column("recovery_classification", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "workflow_sync_records",
        sa.Column("recovery_updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "workflow_sync_records",
        sa.Column("replay_requested_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "workflow_sync_records",
        sa.Column("replay_requested_by", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "workflow_sync_records",
        sa.Column("terminated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "workflow_sync_records",
        sa.Column("termination_reason", sa.Text(), nullable=True),
    )
    op.add_column(
        "workflow_sync_records",
        sa.Column("terminated_after_sync_count", sa.Integer(), nullable=True),
    )
    op.add_column(
        "workflow_sync_records",
        sa.Column("terminated_after_planned_item_key", sa.String(length=255), nullable=True),
    )
    op.alter_column("workflow_sync_records", "lineage_generation", server_default=None)
    op.create_unique_constraint(
        "uq_workflow_sync_record_identity",
        "workflow_sync_records",
        [
            "proposal_artifact_id",
            "proposal_version_number",
            "target_system",
            "sync_kind",
            "planned_item_key",
            "lineage_generation",
        ],
    )


def downgrade() -> None:
    op.drop_constraint("uq_workflow_sync_record_identity", "workflow_sync_records", type_="unique")
    op.create_unique_constraint(
        "uq_workflow_sync_record_identity",
        "workflow_sync_records",
        [
            "proposal_artifact_id",
            "proposal_version_number",
            "target_system",
            "sync_kind",
            "planned_item_key",
        ],
    )
    op.drop_column("workflow_sync_records", "terminated_after_planned_item_key")
    op.drop_column("workflow_sync_records", "terminated_after_sync_count")
    op.drop_column("workflow_sync_records", "termination_reason")
    op.drop_column("workflow_sync_records", "terminated_at")
    op.drop_column("workflow_sync_records", "replay_requested_by")
    op.drop_column("workflow_sync_records", "replay_requested_at")
    op.drop_column("workflow_sync_records", "recovery_updated_at")
    op.drop_column("workflow_sync_records", "recovery_classification")
    op.drop_column("workflow_sync_records", "lineage_generation")
