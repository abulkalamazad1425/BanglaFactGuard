"""Gemini-only photo-card extraction: ocr_extractions -> photocard_extractions.

Photo cards are now submitted as an image only. Gemini reads the headline,
identifies the claimed outlet among the active verified sources and reads the
printed date; those values are stored ONCE, on the submission itself
(headline, claimed_source_id / claimed_source_text, published_date). There is
no OCR path any more.

1. The table is renamed to ``photocard_extractions`` (its primary key,
   foreign key and indexes are renamed with it).
2. OCR-specific and duplicate columns are dropped: raw_extracted_text,
   confirmed_text, ocr_confidence (+ its CHECK), ocr_engine, is_confirmed,
   fallback_used, extraction_warnings, extractor_used, detected_source_text,
   detected_date_text.
3. extraction_model_version -> model_version, extraction_attempts -> attempts.
4. New: status (PENDING | SUCCEEDED | API_FAILED | INVALID_CONTENT, and FAILED
   for legacy OCR-era failures) and failure_code.

Existing rows: status is derived from the old provenance (extractor_used set
-> SUCCEEDED; ocr_engine 'pending' -> PENDING; otherwise FAILED). Every dropped
non-empty value is preserved verbatim under ``extraction_details -> 'legacy'``
so nothing recorded earlier is lost. Legacy submissions keep the claimed
source/date their submitter typed - those were the claim at the time.

Downgrade restores the old table name and columns, refilling them from
``extraction_details -> 'legacy'`` where available.

Revision ID: e5c9a3f7b1d2
Revises: d4b8e1f7a2c5
Create Date: 2026-10-06 18:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "e5c9a3f7b1d2"
down_revision = "d4b8e1f7a2c5"
branch_labels = None
depends_on = None

_LEGACY_COLUMNS = (
    "raw_extracted_text", "confirmed_text", "ocr_confidence", "ocr_engine", "is_confirmed",
    "fallback_used", "extraction_warnings", "extractor_used", "detected_source_text", "detected_date_text",
)


def upgrade() -> None:
    op.rename_table("ocr_extractions", "photocard_extractions")
    op.execute("ALTER TABLE photocard_extractions RENAME CONSTRAINT ocr_extractions_pkey TO photocard_extractions_pkey")
    op.execute(
        "ALTER TABLE photocard_extractions RENAME CONSTRAINT ocr_extractions_submission_id_fkey "
        "TO photocard_extractions_submission_id_fkey"
    )
    op.execute("ALTER INDEX ix_ocr_extractions_created_at RENAME TO ix_photocard_extractions_created_at")
    op.execute("ALTER INDEX ix_ocr_extractions_submission_id RENAME TO ix_photocard_extractions_submission_id")

    op.add_column("photocard_extractions", sa.Column(
        "status", sa.String(20), nullable=False, server_default="PENDING",
        comment=(
            "PENDING | SUCCEEDED | API_FAILED (every Gemini request failed) | "
            "INVALID_CONTENT (no headline or no active verified source on the card) | "
            "FAILED (legacy OCR-era failure)"
        ),
    ))
    op.add_column("photocard_extractions", sa.Column(
        "failure_code", sa.String(40), nullable=True,
        comment="gemini_unavailable | headline_missing | source_not_identified | headline_and_source_missing",
    ))
    op.alter_column("photocard_extractions", "extraction_model_version", new_column_name="model_version",
                    comment="Gemini model id that read the card.")
    op.alter_column("photocard_extractions", "extraction_attempts", new_column_name="attempts",
                    comment="Gemini requests made for this card (first request included, at most 9).")

    # Status from the old provenance; dropped values preserved under 'legacy'.
    op.execute("""
        UPDATE photocard_extractions SET
          status = CASE
            WHEN extractor_used IS NOT NULL THEN 'SUCCEEDED'
            WHEN ocr_engine = 'pending' THEN 'PENDING'
            ELSE 'FAILED'
          END,
          failure_code = CASE
            WHEN extractor_used IS NULL AND ocr_engine <> 'pending' THEN 'legacy_extraction_failed'
          END,
          extraction_details = COALESCE(extraction_details, '{}'::jsonb) || jsonb_build_object(
            'legacy', jsonb_strip_nulls(jsonb_build_object(
              'extractor_used', extractor_used,
              'fallback_used', fallback_used,
              'ocr_engine', NULLIF(ocr_engine, 'pending'),
              'ocr_confidence', ocr_confidence,
              'raw_extracted_text', NULLIF(raw_extracted_text, ''),
              'confirmed_text', confirmed_text,
              'extraction_warnings', extraction_warnings,
              'detected_source_text', detected_source_text,
              'detected_date_text', detected_date_text
            ))
          )
    """)

    op.drop_constraint("ck_ocr_extractions_confidence_range", "photocard_extractions", type_="check")
    for column in _LEGACY_COLUMNS:
        op.drop_column("photocard_extractions", column)
    op.alter_column("photocard_extractions", "extraction_details", comment=(
        "Provenance: per-attempt Gemini outcomes, the validated raw response "
        "(headline, source id + visible evidence, date as printed) and the parsed "
        "date. Legacy OCR-era values are kept under 'legacy'."
    ))


def downgrade() -> None:
    op.add_column("photocard_extractions", sa.Column("raw_extracted_text", sa.Text(), nullable=False, server_default=""))
    op.add_column("photocard_extractions", sa.Column("confirmed_text", sa.Text(), nullable=True))
    op.add_column("photocard_extractions", sa.Column("ocr_confidence", sa.Float(), nullable=True))
    op.add_column("photocard_extractions", sa.Column("ocr_engine", sa.String(100), nullable=False, server_default="not_run"))
    op.add_column("photocard_extractions", sa.Column("is_confirmed", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("photocard_extractions", sa.Column("fallback_used", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("photocard_extractions", sa.Column("extraction_warnings", JSONB, nullable=True))
    op.add_column("photocard_extractions", sa.Column("extractor_used", sa.String(30), nullable=True))
    op.add_column("photocard_extractions", sa.Column("detected_source_text", sa.Text(), nullable=True))
    op.add_column("photocard_extractions", sa.Column("detected_date_text", sa.Text(), nullable=True))
    op.execute("""
        UPDATE photocard_extractions SET
          raw_extracted_text = COALESCE(extraction_details #>> '{legacy,raw_extracted_text}', ''),
          confirmed_text = extraction_details #>> '{legacy,confirmed_text}',
          ocr_confidence = (extraction_details #>> '{legacy,ocr_confidence}')::double precision,
          ocr_engine = COALESCE(extraction_details #>> '{legacy,ocr_engine}',
                                CASE WHEN status = 'PENDING' THEN 'pending' ELSE 'not_run' END),
          fallback_used = COALESCE((extraction_details #>> '{legacy,fallback_used}')::boolean, false),
          extraction_warnings = extraction_details #> '{legacy,extraction_warnings}',
          extractor_used = COALESCE(extraction_details #>> '{legacy,extractor_used}',
                                    CASE WHEN status = 'SUCCEEDED' THEN 'GEMINI_IMAGE' END),
          detected_source_text = extraction_details #>> '{legacy,detected_source_text}',
          detected_date_text = COALESCE(extraction_details #>> '{legacy,detected_date_text}',
                                        extraction_details #>> '{response,date}')
    """)
    op.create_check_constraint(
        "ck_ocr_extractions_confidence_range", "photocard_extractions",
        "ocr_confidence IS NULL OR (ocr_confidence >= 0.0 AND ocr_confidence <= 1.0)",
    )
    op.alter_column("photocard_extractions", "attempts", new_column_name="extraction_attempts")
    op.alter_column("photocard_extractions", "model_version", new_column_name="extraction_model_version")
    op.drop_column("photocard_extractions", "failure_code")
    op.drop_column("photocard_extractions", "status")
    op.execute("ALTER INDEX ix_photocard_extractions_submission_id RENAME TO ix_ocr_extractions_submission_id")
    op.execute("ALTER INDEX ix_photocard_extractions_created_at RENAME TO ix_ocr_extractions_created_at")
    op.execute(
        "ALTER TABLE photocard_extractions RENAME CONSTRAINT photocard_extractions_submission_id_fkey "
        "TO ocr_extractions_submission_id_fkey"
    )
    op.execute("ALTER TABLE photocard_extractions RENAME CONSTRAINT photocard_extractions_pkey TO ocr_extractions_pkey")
    op.rename_table("photocard_extractions", "ocr_extractions")
