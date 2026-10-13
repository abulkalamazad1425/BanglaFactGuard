from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision = "d7e3b5f0a1c6"
down_revision = "c4a2d8f1e9b3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OVERALL_VERDICT_ENUM = sa.Enum(
    "FAKE", "REAL", "MISLEADING", "ALTERED", name="overall_verdict_enum"
)


def upgrade() -> None:
    bind = op.get_bind()
    OVERALL_VERDICT_ENUM.create(bind, checkfirst=True)

    op.add_column(
        "expert_reviews_v2",
        sa.Column(
            "ai_overall_verdict",
            sa.Enum(name="overall_verdict_enum", create_type=False),
            nullable=True,
        ),
    )
    op.add_column(
        "expert_reviews_v2",
        sa.Column(
            "vote_overall_verdict",
            sa.Enum(name="overall_verdict_enum", create_type=False),
            nullable=True,
        ),
    )
    op.alter_column("expert_reviews_v2", "ai_source_status", nullable=True)
    op.alter_column("expert_reviews_v2", "vote_source_status", nullable=True)

    op.execute(
        """
        UPDATE expert_reviews_v2
        SET
            ai_overall_verdict = CASE
                WHEN ai_source_status = 'NOT_FOUND' THEN 'FAKE'::overall_verdict_enum
                WHEN ai_content_status = 'ALTERED' THEN 'ALTERED'::overall_verdict_enum
                WHEN ai_date_status = 'MISMATCHED' THEN 'MISLEADING'::overall_verdict_enum
                ELSE 'REAL'::overall_verdict_enum
            END,
            vote_overall_verdict = CASE
                WHEN vote_source_status = 'NOT_FOUND' THEN 'FAKE'::overall_verdict_enum
                WHEN vote_content_status = 'ALTERED' THEN 'ALTERED'::overall_verdict_enum
                WHEN vote_date_status = 'MISMATCHED' THEN 'MISLEADING'::overall_verdict_enum
                ELSE 'REAL'::overall_verdict_enum
            END
        """
    )
    op.alter_column("expert_reviews_v2", "ai_overall_verdict", nullable=False)
    op.alter_column("expert_reviews_v2", "vote_overall_verdict", nullable=False)

    op.add_column(
        "verification_results_v2",
        sa.Column(
            "overall_verdict",
            sa.Enum(name="overall_verdict_enum", create_type=False),
            nullable=True,
        ),
    )
    op.create_index(
        op.f("ix_verification_results_v2_overall_verdict"),
        "verification_results_v2",
        ["overall_verdict"],
        unique=False,
    )
    op.execute(
        """
        UPDATE verification_results_v2 vr
        SET overall_verdict = CASE
            WHEN vr.source_status = 'NOT_FOUND' THEN 'FAKE'::overall_verdict_enum
            WHEN vr.content_status = 'ALTERED' THEN 'ALTERED'::overall_verdict_enum
            WHEN vr.date_status = 'MISMATCHED' THEN 'MISLEADING'::overall_verdict_enum
            WHEN vr.source_status = 'CONFIRMED' THEN 'REAL'::overall_verdict_enum
            ELSE NULL
        END
        FROM submissions s
        WHERE s.id = vr.submission_id AND s.status = 'FINALIZED'
        """
    )

    op.add_column(
        "multimodal_analysis",
        sa.Column(
            "expert_overall_verdict",
            sa.Enum(name="overall_verdict_enum", create_type=False),
            nullable=True,
        ),
    )

    op.create_table(
        "voting_config",
        sa.Column("min_expert_votes", sa.Integer(), nullable=False),
        sa.Column(
            "id",
            sa.UUID(),
            nullable=False,
            comment="Primary key — UUID v4 generated in Python before INSERT",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "min_expert_votes >= 1", name="ck_voting_config_min_votes_positive"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute(
        """
        INSERT INTO voting_config (id, min_expert_votes, created_at, updated_at)
        VALUES (gen_random_uuid(), 3, now(), now())
        """
    )


def downgrade() -> None:
    op.drop_table("voting_config")

    op.drop_column("multimodal_analysis", "expert_overall_verdict")

    op.drop_index(
        op.f("ix_verification_results_v2_overall_verdict"),
        table_name="verification_results_v2",
    )
    op.drop_column("verification_results_v2", "overall_verdict")

    op.alter_column("expert_reviews_v2", "ai_source_status", nullable=False)
    op.alter_column("expert_reviews_v2", "vote_source_status", nullable=False)
    op.drop_column("expert_reviews_v2", "vote_overall_verdict")
    op.drop_column("expert_reviews_v2", "ai_overall_verdict")

    bind = op.get_bind()
    OVERALL_VERDICT_ENUM.drop(bind, checkfirst=True)
