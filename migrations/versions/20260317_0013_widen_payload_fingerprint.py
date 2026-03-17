"""widen payload_fingerprint to text

Calendar sync fingerprints are raw JSON strings that can exceed 128 chars
when event titles are long. varchar(128) was sized for sha256 hashes only.

Revision ID: 20260317_0013
Revises: 20260313_0012
Create Date: 2026-03-17 00:00:00.000000
"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "20260317_0013"
down_revision: str | None = "20260313_0012"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

import sqlalchemy as sa
from alembic import op


def upgrade() -> None:
    op.alter_column(
        "workflow_sync_records",
        "payload_fingerprint",
        type_=sa.Text(),
        existing_type=sa.String(128),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "workflow_sync_records",
        "payload_fingerprint",
        type_=sa.String(128),
        existing_type=sa.Text(),
        existing_nullable=False,
    )
