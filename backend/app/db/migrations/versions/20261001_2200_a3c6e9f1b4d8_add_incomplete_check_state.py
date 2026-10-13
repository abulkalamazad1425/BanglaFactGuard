from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision = "a3c6e9f1b4d8"
down_revision = "f8a1d3c5e7b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE source_status_enum ADD VALUE IF NOT EXISTS 'INCOMPLETE'")
    op.execute("ALTER TYPE content_status_enum ADD VALUE IF NOT EXISTS 'INCOMPLETE'")
    op.execute("ALTER TYPE date_status_enum ADD VALUE IF NOT EXISTS 'INCOMPLETE'")


def downgrade() -> None:
    pass
