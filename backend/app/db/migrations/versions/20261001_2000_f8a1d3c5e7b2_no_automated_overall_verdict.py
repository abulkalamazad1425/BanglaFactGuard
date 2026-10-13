from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision = "f8a1d3c5e7b2"
down_revision = "e2f4c7a9b3d1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("expert_reviews_v2", "ai_overall_verdict", nullable=True)


def downgrade() -> None:
    pass
