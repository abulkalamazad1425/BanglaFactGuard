"""Replace the single TRUE/FALSE/PARTIALLY_TRUE/NOT_FOUND_IN_CLAIMED_SOURCE
verdict with a 3-dimensional model on verification_results_v2:

    source_status  (CONFIRMED | NOT_FOUND)
    content_status (MATCHED | ALTERED, set only when source is CONFIRMED)
    date_status    (MATCHED | MISMATCHED, set only when both dates are known)

final_label is renamed to ai_consensus_label and kept: it now serves only as
the single-category input the pre-existing expert-review weighted-consensus
vote expects (see app/features/verification/verdict_compat.py), not as the
verdict returned to end users. Existing rows are backfilled from their old
final_label value so no verification history is lost; date_status cannot be
backfilled (the source article's publication date was not persisted
separately before this migration) and is left NULL for pre-existing rows.

The legacy (pre-V2) verified_claims/verification_results/expert_reviews
tables and their verification_label_enum type are untouched — expert review
continues to use that enum for its own voting, independent of this change.
"""

revision = "b3f1c9a2d4e7"
down_revision = "9ed4fe39e0e9"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


SOURCE_STATUS_ENUM = postgresql.ENUM(
    "CONFIRMED", "NOT_FOUND", name="source_status_enum"
)
CONTENT_STATUS_ENUM = postgresql.ENUM(
    "MATCHED", "ALTERED", name="content_status_enum"
)
DATE_STATUS_ENUM = postgresql.ENUM(
    "MATCHED", "MISMATCHED", name="date_status_enum"
)


def upgrade() -> None:
    bind = op.get_bind()
    SOURCE_STATUS_ENUM.create(bind, checkfirst=True)
    CONTENT_STATUS_ENUM.create(bind, checkfirst=True)
    DATE_STATUS_ENUM.create(bind, checkfirst=True)

    op.add_column(
        "verification_results_v2",
        sa.Column(
            "source_status",
            postgresql.ENUM(
                "CONFIRMED", "NOT_FOUND", name="source_status_enum", create_type=False
            ),
            nullable=True,
            comment="Does the claimed source carry this story at all?",
        ),
    )
    op.add_column(
        "verification_results_v2",
        sa.Column(
            "content_status",
            postgresql.ENUM(
                "MATCHED", "ALTERED", name="content_status_enum", create_type=False
            ),
            nullable=True,
            comment=(
                "How claimed content compares to the source. Only set when "
                "source_status is CONFIRMED."
            ),
        ),
    )
    op.add_column(
        "verification_results_v2",
        sa.Column(
            "date_status",
            postgresql.ENUM(
                "MATCHED", "MISMATCHED", name="date_status_enum", create_type=False
            ),
            nullable=True,
            comment=(
                "Whether the claimed publication date matches the source's "
                "actual date. Independent of content_status."
            ),
        ),
    )

    # Backfill from the old single-category label so existing rows still
    # report a source/content verdict. Date comparison data did not exist
    # before this migration, so date_status stays NULL for old rows.
    op.execute(
        """
        UPDATE verification_results_v2
           SET source_status = CASE
                   WHEN final_label = 'NOT_FOUND_IN_CLAIMED_SOURCE' THEN 'NOT_FOUND'::source_status_enum
                   WHEN final_label IS NOT NULL THEN 'CONFIRMED'::source_status_enum
                   ELSE NULL
               END,
               content_status = CASE
                   WHEN final_label = 'TRUE' THEN 'MATCHED'::content_status_enum
                   WHEN final_label IN ('FALSE', 'PARTIALLY_TRUE') THEN 'ALTERED'::content_status_enum
                   ELSE NULL
               END
        """
    )

    op.drop_index(
        "ix_verification_results_v2_final_label", table_name="verification_results_v2"
    )
    op.drop_index(
        "ix_verification_results_v2_label_created", table_name="verification_results_v2"
    )

    op.alter_column(
        "verification_results_v2",
        "final_label",
        new_column_name="ai_consensus_label",
        comment=(
            "Single-category projection of (source_status, content_status) used "
            "only to feed the pre-existing expert-review weighted-consensus "
            "voting system. Not the verdict shown to end users."
        ),
    )

    op.create_index(
        op.f("ix_verification_results_v2_source_status"),
        "verification_results_v2",
        ["source_status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_verification_results_v2_ai_consensus_label"),
        "verification_results_v2",
        ["ai_consensus_label"],
        unique=False,
    )
    op.create_index(
        "ix_verification_results_v2_status_created",
        "verification_results_v2",
        ["source_status", "content_status", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_verification_results_v2_status_created", table_name="verification_results_v2"
    )
    op.drop_index(
        op.f("ix_verification_results_v2_ai_consensus_label"),
        table_name="verification_results_v2",
    )
    op.drop_index(
        op.f("ix_verification_results_v2_source_status"),
        table_name="verification_results_v2",
    )

    op.alter_column(
        "verification_results_v2",
        "ai_consensus_label",
        new_column_name="final_label",
        comment=None,
    )

    op.create_index(
        "ix_verification_results_v2_label_created",
        "verification_results_v2",
        ["final_label", "created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_verification_results_v2_final_label"),
        "verification_results_v2",
        ["final_label"],
        unique=False,
    )

    op.drop_column("verification_results_v2", "date_status")
    op.drop_column("verification_results_v2", "content_status")
    op.drop_column("verification_results_v2", "source_status")

    bind = op.get_bind()
    DATE_STATUS_ENUM.drop(bind, checkfirst=True)
    CONTENT_STATUS_ENUM.drop(bind, checkfirst=True)
    SOURCE_STATUS_ENUM.drop(bind, checkfirst=True)
