

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
