from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "b7d2e4f6a8c1"
down_revision = "a3c6e9f1b4d8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "verification_results_v2",
        sa.Column("manipulation_flags", JSONB, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("verification_results_v2", "manipulation_flags")
