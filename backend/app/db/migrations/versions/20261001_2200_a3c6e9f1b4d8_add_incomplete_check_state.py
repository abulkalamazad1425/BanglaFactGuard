"""Add INCOMPLETE as a third value to source_status_enum / content_status_enum
/ date_status_enum.

Business rule: a search/retrieval/extraction failure must never be reported
as a confident negative result. Previously, source_status could only be
CONFIRMED or NOT_FOUND — a total search-provider outage and a clean,
thorough, genuinely-empty search were indistinguishable, and both collapsed
to NOT_FOUND. INCOMPLETE now represents "the check could not be completed",
distinct from "the check completed and found nothing" (NOT_FOUND) or "the
check completed and found something" (CONFIRMED/MATCHED/MISMATCHED).

content_status/date_status gain the same third value for the analogous
reason: evidence needed to compare content, or to compare dates, may itself
be unavailable (unextractable article body, missing/ambiguous publication
date) independent of whether the source was confirmed.

Postgres allows ALTER TYPE ... ADD VALUE inside a transaction (PG 12+); this
migration only adds the enum labels and backfills nothing, so there is no
same-transaction "unsafe use of new enum value" conflict.
"""

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
    # Postgres has no DROP VALUE for enums — removing a label requires
    # rebuilding the type (rename old, create new without the value, cast
    # every dependent column, drop old). Not implemented: if any row has
    # been persisted with INCOMPLETE, a straight rebuild would fail anyway,
    # and this migration never backfills INCOMPLETE itself. Treat this
    # migration as effectively one-way.
    pass
