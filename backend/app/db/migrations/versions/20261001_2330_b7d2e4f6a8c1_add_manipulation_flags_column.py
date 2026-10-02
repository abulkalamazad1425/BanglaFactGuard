"""Durably persist S10's manipulation-detection result.

manipulation_flags (the 4 booleans plus the newly-added alteration-detail
lists — which claimed numbers weren't found in the article and the closest
number it did contain, which same-type entities were substituted) previously
lived only in the Redis result cache, written by
PersistenceStage._update_redis_cache. Once that cache entry's TTL expired,
GET /verify/{id} and the photo-card equivalent would silently fall back to
an all-False ManipulationFlagsSchema() — an older claim would appear to have
no detected manipulation even when the original run found some, with nothing
for an expert reviewing it later to see. This column is the durable,
authoritative source going forward; the Redis cache remains a fast-path
best-effort read for a result that was only just computed.

No backfill: historical rows have no manipulation_flags to recover (it was
never persisted), so they read back as NULL and the application falls back
to the legacy Redis-cache-or-empty behaviour for exactly those rows.
"""

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
