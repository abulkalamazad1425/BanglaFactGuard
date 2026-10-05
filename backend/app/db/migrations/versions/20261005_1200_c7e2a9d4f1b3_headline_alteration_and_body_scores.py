"""Headline Alteration + body similarity scores; Gemini-first photo-card extraction.

1. Purges every submission and the data that exists only because of a
   submission: verification results/jobs, retrieved articles, search queries,
   OCR/extraction records, expert reviews, multimodal analyses, result
   deliveries and the submission notifications. Results computed by the old
   comparison logic must not survive as if they were Headline Alteration
   results. Users, verified sources, voting configuration, credibility
   tiers, expert profiles, tokens and every other table are NOT touched.
2. content_status_enum loses INCOMPLETE: the headline verdict is only
   MATCHED or ALTERED (a missing verdict is NULL + headline_check_status).
3. verification_results: drops the retired score columns (semantic/entity/
   contradiction/keyword/numerical/body/passage scores, manipulation_flags)
   and adds headline_check_status, headline_exact_match,
   body_comparison_status.
4. ocr_extractions: adds extraction_attempts, fallback_used,
   extraction_details; widens detected_source_text/detected_date_text to TEXT
   so raw extracted values are never truncated.

Downgrade restores the schema only; purged data cannot be restored.

Revision ID: c7e2a9d4f1b3
Revises: b2f8a4d6c9e1
Create Date: 2026-10-05 12:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "c7e2a9d4f1b3"
down_revision = "b2f8a4d6c9e1"
branch_labels = None
depends_on = None

_SUBMISSION_NOTIFICATION_TYPES = (
    "VERIFICATION_COMPLETE",
    "VERIFICATION_FAILED",
    "EXPERT_REVIEW_AVAILABLE",
    "EXPERT_REVIEW_COMPLETE",
)

_CONTENT_COLUMNS = (
    ("verification_results", "content_status"),
    ("verification_results", "final_content_status"),
    ("expert_reviews", "ai_content_status"),
    ("expert_reviews", "vote_content_status"),
)

_DROPPED_SCORE_COLUMNS = (
    "semantic_similarity",
    "entity_match",
    "contradiction_score",
    "keyword_overlap",
    "numerical_consistency",
    "body_similarity",
    "passage_similarity",
    "body_keyword_coverage",
)


def _purge_submission_data() -> None:
    types = ", ".join(f"'{t}'" for t in _SUBMISSION_NOTIFICATION_TYPES)
    op.execute(
        f"DELETE FROM notifications WHERE notification_type IN ({types}) "
        "OR link_url LIKE '/verify/%' OR link_url LIKE '/expert/queue/%'"
    )
    for table in (
        "result_deliveries",
        "verification_jobs",
        "expert_reviews",
        "verification_results",
        "source_evidence_queries",
        "retrieved_articles",
        "ocr_extractions",
    ):
        op.execute(f"DELETE FROM {table}")
    op.execute("UPDATE multimodal_analysis SET is_duplicate_of_id = NULL")
    op.execute("DELETE FROM multimodal_analysis")
    op.execute("UPDATE submissions SET duplicate_of_submission_id = NULL")
    op.execute("DELETE FROM submissions")


def _recreate_content_enum(values: tuple[str, ...]) -> None:
    op.execute("ALTER TYPE content_status_enum RENAME TO content_status_enum_old")
    op.execute(f"CREATE TYPE content_status_enum AS ENUM ({', '.join(repr(v) for v in values)})")
    for table, column in _CONTENT_COLUMNS:
        op.execute(
            f"ALTER TABLE {table} ALTER COLUMN {column} TYPE content_status_enum "
            f"USING {column}::text::content_status_enum"
        )
    op.execute("DROP TYPE content_status_enum_old")


def upgrade() -> None:
    _purge_submission_data()
    _recreate_content_enum(("MATCHED", "ALTERED"))

    op.drop_constraint("ck_verification_results_semantic_similarity_range", "verification_results", type_="check")
    op.drop_constraint("ck_verification_results_contradiction_score_range", "verification_results", type_="check")
    for column in _DROPPED_SCORE_COLUMNS:
        op.drop_column("verification_results", column)
    op.drop_column("verification_results", "manipulation_flags")
    op.add_column("verification_results", sa.Column(
        "headline_check_status", sa.String(32), nullable=True,
        comment="COMPLETED | SOURCE_NOT_FOUND | SOURCE_CHECK_INCOMPLETE | SOURCE_TITLE_MISSING | MODEL_UNAVAILABLE | UNDETERMINED",
    ))
    op.add_column("verification_results", sa.Column(
        "headline_exact_match", sa.Boolean(), nullable=True,
        comment="True when the headline verdict came from an exact match with the source title.",
    ))
    op.add_column("verification_results", sa.Column(
        "body_comparison_status", sa.String(24), nullable=True,
        comment="COMPUTED | SKIPPED | UNAVAILABLE (scores in analysis_details.body_similarity)",
    ))

    op.add_column("ocr_extractions", sa.Column(
        "extraction_attempts", sa.Integer(), nullable=True,
        comment="Gemini attempts made for this card (first request included, at most 3).",
    ))
    op.add_column("ocr_extractions", sa.Column(
        "fallback_used", sa.Boolean(), nullable=False, server_default=sa.text("false"),
        comment="True when EasyOCR + the deterministic fallback extractor ran.",
    ))
    op.add_column("ocr_extractions", sa.Column(
        "extraction_details", postgresql.JSONB(), nullable=True,
        comment="Per-attempt Gemini outcomes, raw validated Gemini fields, fallback OCR engine, failure reason.",
    ))
    op.alter_column("ocr_extractions", "detected_source_text", type_=sa.Text(), existing_type=sa.String(255))
    op.alter_column("ocr_extractions", "detected_date_text", type_=sa.Text(), existing_type=sa.String(255))


def downgrade() -> None:
    op.alter_column("ocr_extractions", "detected_date_text", type_=sa.String(255), existing_type=sa.Text(),
                    postgresql_using="left(detected_date_text, 255)")
    op.alter_column("ocr_extractions", "detected_source_text", type_=sa.String(255), existing_type=sa.Text(),
                    postgresql_using="left(detected_source_text, 255)")
    op.drop_column("ocr_extractions", "extraction_details")
    op.drop_column("ocr_extractions", "fallback_used")
    op.drop_column("ocr_extractions", "extraction_attempts")

    op.drop_column("verification_results", "body_comparison_status")
    op.drop_column("verification_results", "headline_exact_match")
    op.drop_column("verification_results", "headline_check_status")
    op.add_column("verification_results", sa.Column("manipulation_flags", postgresql.JSONB(), nullable=True))
    for column in _DROPPED_SCORE_COLUMNS:
        op.add_column("verification_results", sa.Column(column, sa.Float(), nullable=True))
    op.create_check_constraint(
        "ck_verification_results_semantic_similarity_range", "verification_results",
        "semantic_similarity IS NULL OR (semantic_similarity >= 0.0 AND semantic_similarity <= 1.0)",
    )
    op.create_check_constraint(
        "ck_verification_results_contradiction_score_range", "verification_results",
        "contradiction_score IS NULL OR (contradiction_score >= 0.0 AND contradiction_score <= 1.0)",
    )
    _recreate_content_enum(("MATCHED", "ALTERED", "INCOMPLETE"))
