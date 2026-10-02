"""Scope-aware component scores, durable result analysis, and durable jobs.

* verification_results_v2 gains the applicable component scores that used to
  live only in Redis (headline/body/passage similarity, keyword coverages),
  the claim scope and pipeline version they were computed under, and an
  `analysis_details` JSONB with metric states, check states, selected
  evidence, NLI output, search accounting and date provenance. Results can
  therefore be shown identically right after verification, after navigating
  away, after Redis expiry, and via the database cache fallback.
* `pipeline_version` / `claim_scope` are NULL on historical rows. Those rows
  are kept (nothing is deleted or rewritten) but are never served as fresh
  results: the pipeline version is part of claim identity, so identity hashes
  computed by the corrected code differ from every historical hash.
* `reused_from_submission_id` records that a result row is an automated-result
  copy of an earlier identical verification (the requester still gets their
  own submission row — owner, photo-card image and OCR record intact).
* submissions gains `processing_phase` and `failure_reason` so a pending or
  failed submission can render a useful state without a result row.
* verification_jobs is the durable work queue behind background verification
  (text and photo-card): written in the same transaction as the accepted
  submission, claimed with FOR UPDATE SKIP LOCKED, reclaimed when a lock goes
  stale after a restart.

ai_consensus_label is intentionally left in place (historical data) but is no
longer written: the automated system casts no overall truth vote.
"""

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

    # Restart-recovery backstop for rows accepted before jobs existed:
    # text submissions left PENDING/PROCESSING are re-queued (everything the
    # job needs is on the submission row); photo cards from the old
    # synchronous flow have no stored job inputs, so they are failed with a
    # reason instead of spinning forever.
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
