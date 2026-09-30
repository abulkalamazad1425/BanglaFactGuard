from __future__ import annotations

import uuid
from dataclasses import dataclass

import pytest

from app.features.photocard.source_detector import (
    SourceDetector,
    _best_window_ratio,
    _extract_domains,
    _normalise,
)

THRESHOLD = 0.82


@dataclass
class FakeSource:
    """Stands in for a VerifiedSource row without touching the database."""

    canonical_name: str
    display_name: str
    display_name_en: str | None
    aliases: list[str]
    base_url: str
    id: uuid.UUID = uuid.uuid4()


class FakeSourceRepo:
    def __init__(self, sources: list[FakeSource]) -> None:
        self._sources = sources

    async def list_active(self, *, limit: int = 100, offset: int = 0):
        return self._sources[offset : offset + limit]


PROTHOM_ALO = FakeSource(
    canonical_name="prothomalo.com",
    display_name="প্রথম আলো",
    display_name_en="Prothom Alo",
    aliases=["প্রথম আলো", "prothom alo", "prothomalo"],
    base_url="https://www.prothomalo.com",
    id=uuid.uuid4(),
)
KALER_KANTHO = FakeSource(
    canonical_name="kalerkantho.com",
    display_name="কালের কণ্ঠ",
    display_name_en="Kaler Kantho",
    aliases=["কালের কণ্ঠ", "kaler kantho"],
    base_url="https://www.kalerkantho.com",
    id=uuid.uuid4(),
)


@pytest.fixture
def detector() -> SourceDetector:
    return SourceDetector(FakeSourceRepo([PROTHOM_ALO, KALER_KANTHO]))


class TestDetection:
    @pytest.mark.asyncio
    async def test_exact_bangla_banner(self, detector: SourceDetector) -> None:
        results = await detector.detect(
            "প্রথম আলো\nবাংলাদেশে নতুন আইন পাস", threshold=THRESHOLD
        )

        assert results
        assert results[0].canonical_name == "prothomalo.com"
        assert results[0].method == "exact"

    @pytest.mark.asyncio
    async def test_url_wins_as_domain_match(self, detector: SourceDetector) -> None:
        results = await detector.detect(
            "নতুন আইন পাস\nwww.prothomalo.com", threshold=THRESHOLD
        )

        assert results[0].canonical_name == "prothomalo.com"
        assert results[0].method == "domain"
        assert results[0].confidence == pytest.approx(1.0)

    @pytest.mark.asyncio
    async def test_ocr_garbled_banner_matches_fuzzily(
        self, detector: SourceDetector
    ) -> None:
        # "আলো" → "আল৷": a lost matra, the most common Bangla OCR error.
        # Exact matching would miss a perfectly legible banner.
        results = await detector.detect(
            "প্রথম আল৷ | ব্রেকিং নিউজ", threshold=THRESHOLD
        )

        assert results
        assert results[0].canonical_name == "prothomalo.com"
        assert results[0].method == "fuzzy"

    @pytest.mark.asyncio
    async def test_unbranded_card_detects_nothing(
        self, detector: SourceDetector
    ) -> None:
        results = await detector.detect(
            "সরকার আজ নতুন সিদ্ধান্ত নিয়েছে বলে জানা গেছে", threshold=THRESHOLD
        )

        assert results == []

    @pytest.mark.asyncio
    async def test_empty_text_detects_nothing(self, detector: SourceDetector) -> None:
        assert await detector.detect("   ", threshold=THRESHOLD) == []

    @pytest.mark.asyncio
    async def test_results_are_ranked_by_confidence(
        self, detector: SourceDetector
    ) -> None:
        results = await detector.detect(
            "প্রথম আলো এবং কালের কণ্ঠ", threshold=THRESHOLD
        )

        confidences = [item.confidence for item in results]
        assert confidences == sorted(confidences, reverse=True)


class TestMatchingHelpers:
    def test_extract_domains(self) -> None:
        assert _extract_domains("দেখুন https://www.prothomalo.com/news/1") == {
            "prothomalo.com"
        }
        assert _extract_domains("কোনো লিংক নেই") == set()

    def test_window_ratio_rejects_unrelated_source(self) -> None:
        haystack = _normalise("প্রথম আলো বাংলাদেশে নতুন আইন")
        score, _ = _best_window_ratio(haystack, _normalise("কালের কণ্ঠ"))

        assert score < THRESHOLD

    def test_window_ratio_tolerates_a_garbled_glyph(self) -> None:
        haystack = _normalise("প্রথম আল৷ | ব্রেকিং")
        score, _ = _best_window_ratio(haystack, _normalise("প্রথম আলো"))

        assert score >= THRESHOLD

    def test_window_ratio_handles_empty_input(self) -> None:
        assert _best_window_ratio("", "প্রথম আলো") == (0.0, "")
        assert _best_window_ratio("প্রথম আলো", "") == (0.0, "")
