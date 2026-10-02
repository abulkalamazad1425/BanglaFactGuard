"""Record photo-card extraction provenance on ocr_extractions.

The unattended Gemini extraction flow (gemini_extractor.py) needs somewhere
to record which extractor actually produced the final headline (Gemini vs
the existing deterministic fallback), the Gemini model version used, any
extraction-time warnings, and any image-detected source/date text — kept
separately from the user's own claimed_source_text/published_date on
submissions, since those user-provided values are the verification targets
and must never be silently overwritten by what the card's own text implies.
A conflict between the two is recorded in extraction_warnings, not resolved.

No backfill: historical rows predate this flow and have nothing to recover
for these columns; they read back as NULL.
"""

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
