"""
tests/unit/test_photocard_extraction_failure.py
==================================================
Business rule: if neither Gemini nor the deterministic fallback produces a
usable headline, that is an explicit extraction failure — never reported as
Source Not Found or a content_status of ALTERED (those describe a claim
that was checked and found wanting; here there was no claim to check at
all). Nothing should be persisted for a failed extraction.

Also covers the source/date conflict-detection helpers: image-detected
source/date text is recorded and surfaced, never silently substituted for
the user's own claimed_source_text/published_date.
"""

import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import PhotoCardExtractionFailedError
from app.features.photocard.gemini_extractor import HeadlineExtraction
from app.features.photocard.ocr_service import OcrLine, OcrOutput
from app.features.photocard.service import (
    PhotoCardService,
    _date_text_conflicts,
    _detect_conflicts,
    _source_text_conflicts,
)


# ─── Extraction failure — explicit, terminal, never miscategorised ──────
#
# The end-to-end version of this rule (a stored card whose headline cannot be
# extracted ends FAILED with a reason, with no automated check ever run) is
# covered against a real database in test_photocard_background.py. Here: the
# exception type that carries it, and that the sync endpoint maps it to 422.


def test_extraction_failure_is_a_422_distinct_from_source_not_found():
    from app.core.exceptions import SourceNotFoundError

    exc = PhotoCardExtractionFailedError("অস্পষ্ট টেক্সট", ["No Bangla claim text survived cleaning."])
    assert exc.http_status_code == 422
    assert not isinstance(exc, SourceNotFoundError)
    assert "headline" in exc.message.lower()


# ─── Conflict detection ──────────────────────────────────────────────────


def test_source_conflict_detected_when_unrelated():
    assert _source_text_conflicts("বিবিসি বাংলা", "prothomalo.com") is True


def test_source_no_conflict_when_substring_match():
    assert _source_text_conflicts("prothomalo", "prothomalo.com") is False


def test_source_no_conflict_when_identical():
    assert _source_text_conflicts("prothomalo.com", "prothomalo.com") is False


def test_date_conflict_when_year_absent():
    assert _date_text_conflicts("১৫ মার্চ ২০২৪", date(2026, 5, 20)) is True


def test_date_no_conflict_when_year_present():
    assert _date_text_conflicts("১৫ মার্চ ২০২৬", date(2026, 5, 20)) is False


def test_date_no_conflict_when_text_has_no_digits():
    assert _date_text_conflicts("গতকাল", date(2026, 5, 20)) is False


def test_detect_conflicts_surfaces_both_when_both_disagree():
    extraction = HeadlineExtraction(
        headline="একটি শিরোনাম",
        detected_source_text="বিবিসি বাংলা",
        detected_date_text="১৫ মার্চ ২০২৪",
        warnings=[],
        extractor_used="GEMINI",
        model_version="gemini-2.0-flash",
    )
    warnings = _detect_conflicts(extraction, "prothomalo.com", date(2026, 5, 20))
    assert len(warnings) == 2


def test_detect_conflicts_empty_when_nothing_detected():
    extraction = HeadlineExtraction(
        headline="একটি শিরোনাম",
        detected_source_text=None,
        detected_date_text=None,
        warnings=[],
        extractor_used="EXISTING_FALLBACK",
        model_version=None,
    )
    assert _detect_conflicts(extraction, "prothomalo.com", date(2026, 5, 20)) == []


def test_detect_conflicts_empty_when_matching():
    extraction = HeadlineExtraction(
        headline="একটি শিরোনাম",
        detected_source_text="prothomalo.com",
        detected_date_text="২০২৬ সালের ২০ মে",
        warnings=[],
        extractor_used="GEMINI",
        model_version="gemini-2.0-flash",
    )
    assert _detect_conflicts(extraction, "prothomalo.com", date(2026, 5, 20)) == []
