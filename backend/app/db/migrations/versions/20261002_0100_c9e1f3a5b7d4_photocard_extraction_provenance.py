from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "c9e1f3a5b7d4"
down_revision = "b7d2e4f6a8c1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "ocr_extractions", sa.Column("extractor_used", sa.String(30), nullable=True)
    )
    op.add_column(
        "ocr_extractions",
        sa.Column("extraction_model_version", sa.String(100), nullable=True),
    )
    op.add_column(
        "ocr_extractions", sa.Column("extraction_warnings", JSONB, nullable=True)
    )
    op.add_column(
        "ocr_extractions", sa.Column("detected_source_text", sa.String(255), nullable=True)
    )
    op.add_column(
        "ocr_extractions", sa.Column("detected_date_text", sa.String(255), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("ocr_extractions", "detected_date_text")
    op.drop_column("ocr_extractions", "detected_source_text")
    op.drop_column("ocr_extractions", "extraction_warnings")
    op.drop_column("ocr_extractions", "extraction_model_version")
    op.drop_column("ocr_extractions", "extractor_used")
