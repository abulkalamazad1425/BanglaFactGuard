from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "e2f4c7a9b3d1"
down_revision = "d7e3b5f0a1c6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "verification_results_v2",
        sa.Column(
            "final_source_status",
            sa.Enum(name="source_status_enum", create_type=False),
            nullable=True,
        ),
    )
    op.add_column(
        "verification_results_v2",
        sa.Column(
            "final_content_status",
            sa.Enum(name="content_status_enum", create_type=False),
            nullable=True,
        ),
    )
    op.add_column(
        "verification_results_v2",
        sa.Column(
            "final_date_status",
            sa.Enum(name="date_status_enum", create_type=False),
            nullable=True,
        ),
    )
    op.add_column(
        "verification_results_v2",
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.add_column(
        "multimodal_analysis",
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.add_column(
        "voting_config",
        sa.Column(
            "activation_threshold_votes",
            sa.Integer(),
            nullable=False,
            server_default="10",
        ),
    )
    op.add_column(
        "voting_config",
        sa.Column(
            "verified_threshold", sa.Float(), nullable=False, server_default="5.0"
        ),
    )
    op.add_column(
        "voting_config",
        sa.Column("lead_margin", sa.Float(), nullable=False, server_default="1.0"),
    )
    op.add_column(
        "voting_config", sa.Column("max_review_votes", sa.Integer(), nullable=True)
    )
    op.add_column(
        "voting_config", sa.Column("max_review_hours", sa.Integer(), nullable=True)
    )
    op.add_column(
        "voting_config", sa.Column("max_tier_weight", sa.Float(), nullable=True)
    )
    op.create_check_constraint(
        "ck_voting_config_activation_threshold_nonneg",
        "voting_config",
        "activation_threshold_votes >= 0",
    )
    op.create_check_constraint(
        "ck_voting_config_verified_threshold_positive",
        "voting_config",
        "verified_threshold > 0",
    )
    op.create_check_constraint(
        "ck_voting_config_lead_margin_nonneg", "voting_config", "lead_margin >= 0"
    )

    op.create_table(
        "audit_log",
        sa.Column("actor_id", sa.UUID(), nullable=True),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("submission_id", sa.UUID(), nullable=True),
        sa.Column(
            "details",
            JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
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
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["submission_id"], ["submissions.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_audit_log_actor_id"), "audit_log", ["actor_id"], unique=False
    )
    op.create_index(op.f("ix_audit_log_action"), "audit_log", ["action"], unique=False)
    op.create_index(
        op.f("ix_audit_log_submission_id"), "audit_log", ["submission_id"], unique=False
    )
    op.create_index(
        op.f("ix_audit_log_created_at"), "audit_log", ["created_at"], unique=False
    )


def downgrade() -> None:
    op.drop_table("audit_log")

    op.drop_constraint("ck_voting_config_lead_margin_nonneg", "voting_config", type_="check")
    op.drop_constraint(
        "ck_voting_config_verified_threshold_positive", "voting_config", type_="check"
    )
    op.drop_constraint(
        "ck_voting_config_activation_threshold_nonneg", "voting_config", type_="check"
    )
    op.drop_column("voting_config", "max_tier_weight")
    op.drop_column("voting_config", "max_review_hours")
    op.drop_column("voting_config", "max_review_votes")
    op.drop_column("voting_config", "lead_margin")
    op.drop_column("voting_config", "verified_threshold")
    op.drop_column("voting_config", "activation_threshold_votes")

    op.drop_column("multimodal_analysis", "finalized_at")

    op.drop_column("verification_results_v2", "finalized_at")
    op.drop_column("verification_results_v2", "final_date_status")
    op.drop_column("verification_results_v2", "final_content_status")
    op.drop_column("verification_results_v2", "final_source_status")
