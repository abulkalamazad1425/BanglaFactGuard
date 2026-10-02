"""Business-rule correction: the automated system never decides an Overall
verdict (Fake/Real/Misleading/Altered) for SOURCE_BASED or PHOTO_CARD claims.
It only ever produces the three structured checks (source_status/
content_status/date_status) — Overall is exclusively an expert-review outcome
for those two types, with no AI-implied default to vote-tie-break toward or
display as a preliminary suggestion.

expert_reviews_v2.ai_overall_verdict was NOT NULL (a derived "AI-implied
Overall" was snapshotted on every vote, for every submission type). It is
relaxed to nullable here: MULTIMODAL votes continue to populate it (that
model's binary FAKE/NON_FAKE call is a separate, pre-existing, unaffected
design), while SOURCE_BASED/PHOTO_CARD votes going forward leave it NULL.

No backfill: existing SOURCE_BASED/PHOTO_CARD rows keep whatever derived
value they already have (historical data, not erased), consistent with
"do not erase legitimate historical records" — only new rows for these two
types are written with NULL from this point on.
"""

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
    # Historical NULLs (from SOURCE_BASED/PHOTO_CARD votes cast after this
    # migration) have no derivable value to backfill — leaving them NULL
    # would violate a restored NOT NULL constraint, so downgrade is a no-op
    # beyond documenting the intent; a true rollback requires a manual
    # decision on what to backfill those rows with.
    pass
