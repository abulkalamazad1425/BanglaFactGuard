"""Replace expert_reviews_v2's flat (ai_label, expert_label) columns with a
structured vote mirroring the AI pipeline's own (source_status, content_status,
date_status) model:

    ai_source_status / ai_content_status / ai_date_status  — snapshot of the
        AI's call at the moment the expert voted (for accuracy tracking)
    vote_source_status / vote_content_status / vote_date_status — the
        expert's own judgment, with content/date meaningful only when
        vote_source_status is CONFIRMED

This lets experts vote on the same structure the AI produces instead of
collapsing to a single TRUE/FALSE/PARTIALLY_TRUE/NOT_FOUND category, and lets
finalization write the consensus straight back onto
verification_results_v2.source_status/content_status/date_status — no
separate "consensus label" projection is needed for this flow any more.

Existing rows are backfilled on a best-effort basis: old ai_label/expert_label
could not represent a date judgment independent of content, so this backfill
is necessarily lossy (documented inline). This table has no production
traffic yet in this environment, so the lossy backfill is acceptable.

verification_label_enum and VerificationResultV2.ai_consensus_label are left
untouched — the AI pipeline still writes ai_consensus_label when it runs
(app/features/verification/verdict_compat.py), it is simply no longer read or
written by the expert-review finalize path.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision = "c4a2d8f1e9b3"
down_revision = "b3f1c9a2d4e7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "expert_reviews_v2",
        sa.Column(
            "ai_source_status",
            sa.Enum(name="source_status_enum", create_type=False),
            nullable=True,
        ),
    )
    op.add_column(
        "expert_reviews_v2",
        sa.Column(
            "ai_content_status",
            sa.Enum(name="content_status_enum", create_type=False),
            nullable=True,
        ),
    )
    op.add_column(
        "expert_reviews_v2",
        sa.Column(
            "ai_date_status",
            sa.Enum(name="date_status_enum", create_type=False),
            nullable=True,
        ),
    )
    op.add_column(
        "expert_reviews_v2",
        sa.Column(
            "vote_source_status",
            sa.Enum(name="source_status_enum", create_type=False),
            nullable=True,
        ),
    )
    op.add_column(
        "expert_reviews_v2",
        sa.Column(
            "vote_content_status",
            sa.Enum(name="content_status_enum", create_type=False),
            nullable=True,
        ),
    )
    op.add_column(
        "expert_reviews_v2",
        sa.Column(
            "vote_date_status",
            sa.Enum(name="date_status_enum", create_type=False),
            nullable=True,
        ),
    )

    # Best-effort backfill from the old flat columns.
    #   NOT_FOUND_IN_CLAIMED_SOURCE -> source NOT_FOUND, content/date N/A
    #   TRUE                        -> CONFIRMED / MATCHED / MATCHED
    #   FALSE, PARTIALLY_TRUE       -> CONFIRMED / ALTERED / MATCHED (lossy:
    #       the old model could not distinguish "content altered" from
    #       "date mismatched" as independent axes)
    op.execute(
        """
        UPDATE expert_reviews_v2
        SET
            ai_source_status = CASE
                WHEN ai_label = 'NOT_FOUND_IN_CLAIMED_SOURCE' THEN 'NOT_FOUND'::source_status_enum
                ELSE 'CONFIRMED'::source_status_enum
            END,
            ai_content_status = CASE
                WHEN ai_label = 'NOT_FOUND_IN_CLAIMED_SOURCE' THEN NULL
                WHEN ai_label = 'TRUE' THEN 'MATCHED'::content_status_enum
                ELSE 'ALTERED'::content_status_enum
            END,
            ai_date_status = CASE
                WHEN ai_label = 'NOT_FOUND_IN_CLAIMED_SOURCE' THEN NULL
                ELSE 'MATCHED'::date_status_enum
            END,
            vote_source_status = CASE
                WHEN expert_label = 'NOT_FOUND_IN_CLAIMED_SOURCE' THEN 'NOT_FOUND'::source_status_enum
                ELSE 'CONFIRMED'::source_status_enum
            END,
            vote_content_status = CASE
                WHEN expert_label = 'NOT_FOUND_IN_CLAIMED_SOURCE' THEN NULL
                WHEN expert_label = 'TRUE' THEN 'MATCHED'::content_status_enum
                ELSE 'ALTERED'::content_status_enum
            END,
            vote_date_status = CASE
                WHEN expert_label = 'NOT_FOUND_IN_CLAIMED_SOURCE' THEN NULL
                ELSE 'MATCHED'::date_status_enum
            END
        """
    )

    op.alter_column("expert_reviews_v2", "ai_source_status", nullable=False)
    op.alter_column("expert_reviews_v2", "vote_source_status", nullable=False)

    op.drop_column("expert_reviews_v2", "ai_label")
    op.drop_column("expert_reviews_v2", "expert_label")


def downgrade() -> None:
    op.add_column(
        "expert_reviews_v2",
        sa.Column("ai_label", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "expert_reviews_v2",
        sa.Column(
            "expert_label",
            sa.Enum(name="verification_label_enum", create_type=False),
            nullable=True,
        ),
    )

    op.execute(
        """
        UPDATE expert_reviews_v2
        SET
            ai_label = CASE
                WHEN ai_source_status = 'NOT_FOUND' THEN 'NOT_FOUND_IN_CLAIMED_SOURCE'
                WHEN ai_content_status = 'MATCHED' THEN 'TRUE'
                ELSE 'FALSE'
            END,
            expert_label = CASE
                WHEN vote_source_status = 'NOT_FOUND' THEN 'NOT_FOUND_IN_CLAIMED_SOURCE'::verification_label_enum
                WHEN vote_content_status = 'MATCHED' THEN 'TRUE'::verification_label_enum
                ELSE 'FALSE'::verification_label_enum
            END
        """
    )

    op.alter_column("expert_reviews_v2", "ai_label", nullable=False)
    op.alter_column("expert_reviews_v2", "expert_label", nullable=False)

    op.drop_column("expert_reviews_v2", "vote_date_status")
    op.drop_column("expert_reviews_v2", "vote_content_status")
    op.drop_column("expert_reviews_v2", "vote_source_status")
    op.drop_column("expert_reviews_v2", "ai_date_status")
    op.drop_column("expert_reviews_v2", "ai_content_status")
    op.drop_column("expert_reviews_v2", "ai_source_status")
