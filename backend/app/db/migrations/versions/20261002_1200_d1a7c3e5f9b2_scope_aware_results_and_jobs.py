from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "d1a7c3e5f9b2"
down_revision = "c9e1f3a5b7d4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for col in (
        "headline_similarity",
        "body_similarity",
        "passage_similarity",
        "headline_keyword_coverage",
        "passage_keyword_coverage",
        "body_keyword_coverage",
    ):
        op.add_column("verification_results_v2", sa.Column(col, sa.Float(), nullable=True))
    op.add_column(
        "verification_results_v2", sa.Column("claim_scope", sa.String(24), nullable=True)
    )
    op.add_column(
        "verification_results_v2", sa.Column("pipeline_version", sa.String(40), nullable=True)
    )
    op.add_column(
        "verification_results_v2", sa.Column("analysis_details", JSONB, nullable=True)
    )
    op.add_column(
        "verification_results_v2",
        sa.Column(
            "reused_from_submission_id",
            UUID(as_uuid=True),
            sa.ForeignKey("submissions.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    op.add_column("submissions", sa.Column("processing_phase", sa.String(16), nullable=True))
    op.add_column("submissions", sa.Column("failure_reason", sa.Text(), nullable=True))

    op.create_table(
        "verification_jobs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "submission_id",
            UUID(as_uuid=True),
            sa.ForeignKey("submissions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("status", sa.String(12), nullable=False, server_default="QUEUED"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("locked_by", sa.String(64), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("payload", JSONB, nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(
        "ix_verification_jobs_submission_id", "verification_jobs", ["submission_id"], unique=True
    )
    op.create_index("ix_verification_jobs_status", "verification_jobs", ["status"])
    op.create_index("ix_verification_jobs_created_at", "verification_jobs", ["created_at"])
    op.create_index(
        "ix_verification_jobs_status_created", "verification_jobs", ["status", "created_at"]
    )

    op.execute(
        """
        INSERT INTO verification_jobs (id, submission_id, kind, status, attempts, max_attempts)
        SELECT gen_random_uuid(), s.id, 'SOURCE_BASED', 'QUEUED', 0, 3
          FROM submissions s
         WHERE s.status IN ('PENDING', 'PROCESSING')
           AND s.submission_type = 'SOURCE_BASED'
        """
    )
    op.execute(
        """
        UPDATE submissions
           SET status = 'FAILED',
               processing_phase = 'FAILED',
               failure_reason = 'Interrupted before background jobs existed; please resubmit.'
         WHERE status IN ('PENDING', 'PROCESSING')
           AND submission_type = 'PHOTO_CARD'
        """
    )


def downgrade() -> None:
    op.drop_index("ix_verification_jobs_status_created", table_name="verification_jobs")
    op.drop_index("ix_verification_jobs_created_at", table_name="verification_jobs")
    op.drop_index("ix_verification_jobs_status", table_name="verification_jobs")
    op.drop_index("ix_verification_jobs_submission_id", table_name="verification_jobs")
    op.drop_table("verification_jobs")
    op.drop_column("submissions", "failure_reason")
    op.drop_column("submissions", "processing_phase")
    op.drop_column("verification_results_v2", "reused_from_submission_id")
    op.drop_column("verification_results_v2", "analysis_details")
    op.drop_column("verification_results_v2", "pipeline_version")
    op.drop_column("verification_results_v2", "claim_scope")
    for col in (
        "body_keyword_coverage",
        "passage_keyword_coverage",
        "headline_keyword_coverage",
        "passage_similarity",
        "body_similarity",
        "headline_similarity",
    ):
        op.drop_column("verification_results_v2", col)
