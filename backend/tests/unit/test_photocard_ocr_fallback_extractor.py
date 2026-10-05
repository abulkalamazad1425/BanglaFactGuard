from __future__ import annotations

import pytest

from app.features.photocard.ocr_fallback_extractor import (
    bangla_ratio,
    extract_claim,
    normalize_for_match,
)

PROTHOM_ALO_NAMES = ["প্রথম আলো", "Prothom Alo", "prothomalo.com"]


def _lines(*texts: str, confidence: float = 0.9) -> list[tuple[str, float | None]]:
    return [(text, confidence) for text in texts]


class TestNoiseRemoval:
    """Photo-card chrome must never reach the verification pipeline."""

    @pytest.mark.parametrize(
        ("line", "expected_reason"),
        [
            ("ফলো করুন আমাদের পেজ", "social_cta"),
            ("লাইক দিন ও শেয়ার করুন", "social_cta"),
            ("Follow us on Facebook", "social_cta"),
            ("নিজস্ব প্রতিবেদক", "byline"),
            ("অনলাইন ডেস্ক", "byline"),
            ("ছবি: সংগৃহীত", "credit"),
            ("সূত্র: রয়টার্স", "credit"),
            ("১৫ মিনিট আগে", "timestamp"),
            ("প্রকাশ: ১৫ মার্চ ২০২৪", "timestamp"),
            ("১২৩৪ লাইক", "engagement"),
            ("সর্বস্বত্ব সংরক্ষিত", "copyright"),
            ("www.prothomalo.com", "url"),
            ("@prothomalo", "social_handle"),
            ("😀🔥👍", "no_letters"),
            ("BREAKING NEWS UPDATE", "not_bangla"),
            ("১৫ মার্চ ২০২৪", "timestamp"),
        ],
    )
    def test_chrome_line_is_dropped(self, line: str, expected_reason: str) -> None:
        claim = extract_claim(_lines("সরকার নতুন সিদ্ধান্ত ঘোষণা করেছে আজ", line))

        dropped = {item.text: item.noise_reason for item in claim.lines if item.is_noise}
        assert line in dropped
        assert dropped[line] == expected_reason

    def test_low_confidence_line_is_dropped_and_warned(self) -> None:
        claim = extract_claim(
            [
                ("সরকার নতুন সিদ্ধান্ত ঘোষণা করেছে আজ", 0.95),
                ("অস্পষ্ট লেখা যা পড়া যায়নি", 0.10),
            ],
            min_confidence=0.30,
        )

        dropped = [item for item in claim.lines if item.is_noise]
        assert [item.noise_reason for item in dropped] == ["low_confidence"]
        assert any("low confidence" in warning for warning in claim.warnings)

    def test_claim_text_survives(self) -> None:
        headline = "বাংলাদেশে নতুন ডিজিটাল নিরাপত্তা আইন পাস হয়েছে"
        claim = extract_claim(_lines(headline, "ফলো করুন"))

        assert claim.headline == headline
        assert claim.removed_line_count == 1


class TestSourceBannerRemoval:
    """The outlet's own name is attribution, not part of the claim."""

    def test_banner_line_is_stripped(self) -> None:
        claim = extract_claim(
            _lines("প্রথম আলো", "বাংলাদেশে নতুন ডিজিটাল নিরাপত্তা আইন পাস হয়েছে"),
            source_names=PROTHOM_ALO_NAMES,
        )

        assert "প্রথম আলো" not in claim.headline
        assert claim.headline == "বাংলাদেশে নতুন ডিজিটাল নিরাপত্তা আইন পাস হয়েছে"
        banner = next(item for item in claim.lines if item.is_noise)
        assert banner.noise_reason == "source_banner"

    def test_ocr_garbled_banner_is_still_stripped(self) -> None:
        # A dropped matra is the single most common Bangla OCR error; exact
        # matching alone would leave this wordmark inside the claim.
        claim = extract_claim(
            _lines("প্রথম আল৷", "সংসদে নতুন আইন পাস হয়েছে বলে জানা গেছে"),
            source_names=PROTHOM_ALO_NAMES,
        )

        assert "আল৷" not in claim.headline

    def test_headline_mentioning_the_outlet_is_kept(self) -> None:
        # Stripping must be conservative: an outlet named *inside* a sentence
        # is claim content and removing it would change what is verified.
        headline = "প্রথম আলোর প্রতিবেদনে দুর্নীতির নতুন তথ্য উঠে এসেছে বলে দাবি"
        claim = extract_claim(_lines(headline), source_names=PROTHOM_ALO_NAMES)

        assert claim.headline == headline


class TestSegmentation:
    def test_wrapped_headline_lines_are_joined(self) -> None:
        claim = extract_claim(
            _lines(
                "বাংলাদেশে নতুন ডিজিটাল নিরাপত্তা আইন",
                "সংসদে সর্বসম্মতিক্রমে পাস হয়েছে",
            )
        )

        assert claim.headline == (
            "বাংলাদেশে নতুন ডিজিটাল নিরাপত্তা আইন সংসদে সর্বসম্মতিক্রমে পাস হয়েছে"
        )
        assert claim.body is None

    def test_body_prose_is_split_from_headline(self) -> None:
        claim = extract_claim(
            _lines(
                "বাংলাদেশে নতুন ডিজিটাল নিরাপত্তা আইন",
                "সংসদে সর্বসম্মতিক্রমে পাস হয়েছে",
                "আইনটি আগামী ১ জুলাই থেকে কার্যকর হবে বলে জানিয়েছেন আইনমন্ত্রী।",
            )
        )

        assert "কার্যকর" not in claim.headline
        assert claim.body is not None
        assert "কার্যকর" in claim.body

    def test_single_paragraph_card_splits_on_first_sentence(self) -> None:
        claim = extract_claim(
            _lines(
                "সরকার আজ নতুন সিদ্ধান্ত নিয়েছে। "
                "এই সিদ্ধান্ত আগামী মাস থেকে কার্যকর হবে। "
                "সব মন্ত্রণালয়কে নির্দেশ দেওয়া হয়েছে।"
            )
        )

        assert claim.headline == "সরকার আজ নতুন সিদ্ধান্ত নিয়েছে।"
        assert claim.body is not None
        assert "সব মন্ত্রণালয়কে" in claim.body

    def test_danda_is_preserved_for_user_review(self) -> None:
        # The confirmation screen is read against the card itself, so silently
        # rewriting । to . would look like a transcription error.
        claim = extract_claim(_lines("সরকার আজ নতুন সিদ্ধান্ত নিয়েছে।"))

        assert claim.headline.endswith("।")

    def test_card_with_no_bangla_yields_warning_not_garbage(self) -> None:
        claim = extract_claim(_lines("BREAKING NEWS", "@somepage"))

        assert claim.headline == ""
        assert claim.body is None
        assert claim.warnings


class TestHelpers:
    def test_bangla_ratio_ignores_digits_and_punctuation(self) -> None:
        assert bangla_ratio("সরকার ২০২৪ — নতুন!") == pytest.approx(1.0)
        assert bangla_ratio("BREAKING NEWS") == pytest.approx(0.0)
        assert bangla_ratio("") == pytest.approx(0.0)

    def test_normalize_for_match_strips_punctuation_and_case(self) -> None:
        assert normalize_for_match("  Prothom-Alo | প্রথম  আলো! ") == (
            "prothom alo প্রথম আলো"
        )
