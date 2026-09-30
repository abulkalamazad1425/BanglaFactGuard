"""
Turn raw photo-card OCR into a clean, verifiable Bangla claim.

A photo card is mostly *not* the claim. A typical card carries, in reading
order: the outlet's logo and banner text, a headline of one to three lines,
sometimes a supporting sentence, and then a band of chrome — social handles,
"লাইক / শেয়ার / ফলো করুন" calls to action, reporter bylines, photo credits,
timestamps, hashtags and page URLs.

Feeding all of that into the verification pipeline is actively harmful: the
chrome dilutes the embedding, drags entity matching toward the outlet's own
name, and pushes an otherwise-true claim toward NOT_FOUND. So this module does
three things, in order:

1. **Drop non-Bangla lines.** The pipeline only verifies Bangla claims, and
   nearly all Latin text on a Bangla card is chrome (handles, URLs, brand
   marks).
2. **Drop known chrome.** Pattern-matched against the recurring furniture of
   Bangladeshi news photo cards.
3. **Segment what survives** into a headline and a body, because the pipeline
   ranks evidence very differently for the two.

The outlet banner is deliberately *kept in the raw text* — it is removed from
the claim but it is the strongest signal available to
:mod:`source_detector`, which runs against the raw text, not this output.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from Levenshtein import ratio as levenshtein_ratio

from app.shared.utils.bangla_normalizer import normalize_unicode, normalize_whitespace

_LETTER_RE = re.compile(r"[^\W\d_]", re.UNICODE)
_MATCH_PUNCT_RE = re.compile(r"[^\w\sঀ-৿]", re.UNICODE)

# Bangla sentence terminators plus their Latin equivalents, which OCR often
# substitutes for the danda.
_SENTENCE_END_RE = re.compile(r"(?<=[।!?\.])\s+")

_URL_RE = re.compile(
    r"(?:https?://|www\.)\S+|\b[a-z0-9-]+\.(?:com|net|org|tv|bd|info|co)\b(?:/\S*)?",
    re.IGNORECASE,
)
_HANDLE_RE = re.compile(r"[@#][\wঀ-৿._-]+")
_EMOJI_RE = re.compile(
    "[" "\U0001f000-\U0001faff" "☀-➿" "️" "←-⇿" "]+"
)

# Chrome that appears verbatim on Bangladeshi news photo cards. Matched
# case-insensitively against the normalised line.
_NOISE_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "social_cta",
        re.compile(
            r"লাইক\s*(?:দিন|করুন)|শেয়ার\s*করুন|কমেন্ট\s*করুন|ফলো\s*করুন"
            r"|সাবস্ক্রাইব\s*করুন|পেজটি\s*(?:লাইক|ফলো)|ফলো\s*রাখুন"
            r"|বিস্তারিত\s*(?:কমেন্টে|লিংকে)|লিংক\s*কমেন্টে"
            r"|সাথেই\s*থাকুন|আমাদের\s*(?:পেজ|চ্যানেল|সাথে)"
            r"|\b(?:like|share|follow|subscribe|comment|click here|read more|swipe)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "byline",
        re.compile(
            r"নিজস্ব\s*প্রতিবেদক|স্টাফ\s*রিপোর্টার|নিজস্ব\s*সংবাদদাতা"
            r"|অনলাইন\s*ডেস্ক|নিউজ\s*ডেস্ক|আন্তর্জাতিক\s*ডেস্ক|ক্রীড়া\s*ডেস্ক"
            r"|বিনোদন\s*ডেস্ক|ডেস্ক\s*রিপোর্ট|প্রতিবেদক\s*[:：]|সংবাদদাতা\s*[:：]"
            r"|\breporter\b|\bcorrespondent\b|\bdesk report\b",
            re.IGNORECASE,
        ),
    ),
    (
        "credit",
        re.compile(
            r"ছবি\s*[:：]|ফাইল\s*ছবি|প্রতীকী\s*ছবি|সংগৃহীত|গ্রাফিক্স\s*[:：]"
            r"|সূত্র\s*[:：]|তথ্যসূত্র|ইনফোগ্রাফিক|ডিজাইন\s*[:：]"
            r"|\bphoto\s*[:：]|\bsource\s*[:：]|\bcollected\b|\bfile photo\b",
            re.IGNORECASE,
        ),
    ),
    (
        "timestamp",
        re.compile(
            r"(?:প্রকাশ|প্রকাশিত|আপডেট|হালনাগাদ)\s*[:：]"
            r"|[\d০-৯]+\s*(?:মিনিট|ঘণ্টা|ঘন্টা|দিন|সপ্তাহ)\s*আগে"
            r"|\b(?:published|updated)\s*[:：]|\d+\s*(?:minutes?|hours?|days?)\s+ago",
            re.IGNORECASE,
        ),
    ),
    (
        "engagement",
        re.compile(
            r"[\d০-৯]+\s*(?:লাইক|শেয়ার|কমেন্ট|মন্তব্য|ভিউ|রিঅ্যাক্ট)"
            r"|\b\d+[km]?\s*(?:likes?|shares?|comments?|views?|reactions?)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "copyright",
        re.compile(
            r"সর্বস্বত্ব\s*সংরক্ষিত|স্বত্ব\s*©|copyright|all rights reserved|©",
            re.IGNORECASE,
        ),
    ),
    (
        "advert",
        re.compile(r"বিজ্ঞাপন|স্পনসর|প্রমোটেড|\bsponsored\b|\bpromoted\b|\bad\b", re.IGNORECASE),
    ),
]

# Standalone dates ("১৫ মার্চ ২০২৪") and clock times, which are card furniture
# rather than part of the claim. Only stripped when they make up the whole line.
_BANGLA_MONTHS = (
    r"জানুয়ারি|ফেব্রুয়ারি|মার্চ|এপ্রিল|মে|জুন|জুলাই|আগস্ট|সেপ্টেম্বর|অক্টোবর|নভেম্বর|ডিসেম্বর"
)
_DATE_ONLY_RE = re.compile(
    rf"^[\s\d০-৯,./|-]*(?:{_BANGLA_MONTHS})?[\s\d০-৯,./|:-]*"
    r"(?:(?:পূর্বাহ্ণ|অপরাহ্ণ|সকাল|দুপুর|বিকেল|সন্ধ্যা|রাত|am|pm))?[\s\d০-৯,./|:-]*$",
    re.IGNORECASE,
)

_PHONE_RE = re.compile(r"^[\s+\d০-৯()-]{7,}$")

# A claim line shorter than this carries no verifiable proposition on its own.
_MIN_CLAIM_LINE_CHARS = 8
# Below this, a headline is still too fragmentary to stand alone, so the
# extractor keeps absorbing lines even past a sentence boundary.
_MIN_STANDALONE_HEADLINE_CHARS = 25
# Headline blocks longer than this are split — photo-card headlines are short,
# and an over-long "headline" means the card ran the story text together.
_MAX_HEADLINE_CHARS = 220
# A line this close to an outlet's name, once the name is removed, is a
# branding banner rather than claim text.
_BANNER_MATCH_THRESHOLD = 0.78


@dataclass
class ClassifiedLine:
    """One OCR line with the verdict on whether it belongs to the claim."""

    text: str
    confidence: float | None = None
    bangla_ratio: float = 0.0
    is_noise: bool = False
    noise_reason: str | None = None


@dataclass
class ExtractedClaim:
    """The claim recovered from a photo card, ready for user confirmation."""

    headline: str
    body: str | None
    cleaned_text: str
    lines: list[ClassifiedLine] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def kept_lines(self) -> list[ClassifiedLine]:
        return [line for line in self.lines if not line.is_noise]

    @property
    def removed_line_count(self) -> int:
        return sum(1 for line in self.lines if line.is_noise)


def bangla_ratio(text: str) -> float:
    """Fraction of ``text``'s letters that are Bangla (digits/punct excluded)."""
    letters = _LETTER_RE.findall(text)
    if not letters:
        return 0.0
    bangla = sum(1 for char in letters if "ঀ" <= char <= "৿")
    return bangla / len(letters)


def normalize_for_match(text: str) -> str:
    """Case-folded, punctuation-free form used for all fuzzy name matching.

    Shared with :mod:`source_detector` so a banner is measured the same way
    whether it is being detected or being stripped.
    """
    text = unicodedata.normalize("NFC", text).lower()
    return normalize_whitespace(_MATCH_PUNCT_RE.sub(" ", text))


def classify_lines(
    raw_lines: list[tuple[str, float | None]],
    *,
    min_bangla_ratio: float,
    min_confidence: float,
    source_names: list[str] | None = None,
) -> list[ClassifiedLine]:
    """Label every OCR line as claim text or card chrome."""
    classified: list[ClassifiedLine] = []
    banners = [
        normalized
        for normalized in (normalize_for_match(name) for name in source_names or [])
        if len(normalized) >= 3
    ]

    for raw_text, confidence in raw_lines:
        # Deliberately *not* punctuation-normalised: the user is about to read
        # this back against the card, and a danda silently rewritten to a full
        # stop reads as a transcription error. S01 normalises it later anyway.
        text = normalize_whitespace(normalize_unicode(raw_text))
        if not text:
            continue

        line = ClassifiedLine(
            text=text,
            confidence=confidence,
            bangla_ratio=bangla_ratio(text),
        )
        reason = _noise_reason(
            line,
            min_bangla_ratio=min_bangla_ratio,
            min_confidence=min_confidence,
            banners=banners,
        )
        if reason:
            line.is_noise = True
            line.noise_reason = reason
        classified.append(line)

    return classified


def extract_claim(
    raw_lines: list[tuple[str, float | None]],
    *,
    min_bangla_ratio: float = 0.45,
    min_confidence: float = 0.30,
    source_names: list[str] | None = None,
) -> ExtractedClaim:
    """Extract a headline and body from raw OCR lines.

    Segmentation follows how photo cards are actually laid out: the headline is
    the first run of claim lines, and anything after the first visual break is
    supporting body text. When the card is a single unbroken paragraph, the
    first sentence becomes the headline instead.

    ``source_names`` are the outlet names detected on the card. They are
    stripped from the claim: a banner line reading "প্রথম আলো" would otherwise
    end up inside the headline, where it skews entity matching toward the
    outlet's own name and drags the verdict away from the actual claim.
    """
    lines = classify_lines(
        raw_lines,
        min_bangla_ratio=min_bangla_ratio,
        min_confidence=min_confidence,
        source_names=source_names,
    )
    kept = [line.text for line in lines if not line.is_noise]
    warnings: list[str] = []

    if not kept:
        return ExtractedClaim(
            headline="",
            body=None,
            cleaned_text="",
            lines=lines,
            warnings=[
                "No Bangla claim text survived cleaning. The card may be "
                "low-resolution, or its text may not be in Bangla."
            ],
        )

    cleaned_text = "\n".join(kept)
    headline, body = _segment(kept)

    if len(headline) < _MIN_CLAIM_LINE_CHARS:
        warnings.append(
            "The detected headline is very short — please review and correct it "
            "before verifying."
        )
    if any(line.is_noise and line.noise_reason == "low_confidence" for line in lines):
        warnings.append(
            "Some lines were read with low confidence and excluded. Check the "
            "extracted text against the image."
        )

    return ExtractedClaim(
        headline=headline,
        body=body or None,
        cleaned_text=cleaned_text,
        lines=lines,
        warnings=warnings,
    )


def _segment(kept: list[str]) -> tuple[str, str]:
    """Split cleaned claim lines into (headline, body)."""
    if len(kept) == 1:
        return _split_paragraph(kept[0])

    # Grow the headline line by line while it still reads as a headline.
    # Two signals drive the stop, and both come from how Bangla cards are set:
    # a headline wrapped across lines never terminates mid-way, and body prose
    # — unlike a headline — ends its lines with a danda.
    headline_parts: list[str] = [kept[0]]
    index = 1
    while index < len(kept):
        current = " ".join(headline_parts)
        if len(current) >= _MAX_HEADLINE_CHARS:
            break

        standalone = len(current) >= _MIN_STANDALONE_HEADLINE_CHARS
        if standalone and _ends_sentence(headline_parts[-1]):
            break
        if standalone and _ends_sentence(kept[index]):
            break

        headline_parts.append(kept[index])
        index += 1

    headline = " ".join(headline_parts).strip()
    body = " ".join(kept[index:]).strip()

    if len(headline) > _MAX_HEADLINE_CHARS:
        headline, trailing = _split_paragraph(headline)
        body = f"{trailing} {body}".strip()

    return headline, body


def _split_paragraph(text: str) -> tuple[str, str]:
    """Use the first sentence as the headline for single-block cards."""
    sentences = [part.strip() for part in _SENTENCE_END_RE.split(text) if part.strip()]
    if len(sentences) <= 1:
        if len(text) <= _MAX_HEADLINE_CHARS:
            return text.strip(), ""
        # No sentence boundary at all — cut on the last word break in range.
        cut = text.rfind(" ", 0, _MAX_HEADLINE_CHARS)
        cut = cut if cut > _MIN_CLAIM_LINE_CHARS else _MAX_HEADLINE_CHARS
        return text[:cut].strip(), text[cut:].strip()

    headline = sentences[0]
    remaining = sentences[1:]
    # A one-clause opener like "চাঞ্চল্যকর তথ্য।" is a kicker, not the claim —
    # absorb the next sentence so the headline states something verifiable.
    while remaining and len(headline) < _MIN_CLAIM_LINE_CHARS * 2:
        headline = f"{headline} {remaining.pop(0)}"

    return headline.strip(), " ".join(remaining).strip()


def _ends_sentence(text: str) -> bool:
    return text.rstrip().endswith(("।", "!", "?", ".", "…"))


def _is_source_banner(text: str, banners: list[str]) -> bool:
    """Is this line just the outlet's name?

    Deliberately conservative. A headline that *mentions* an outlet
    ("প্রথম আলোর প্রতিবেদনে বলা হয়েছে…") is claim text and must survive, so a
    line only counts as a banner when removing the outlet name leaves it with
    essentially nothing, or when the whole line matches the name closely
    enough to be an OCR-garbled wordmark.
    """
    normalised = normalize_for_match(text)
    if not normalised:
        return False

    for banner in banners:
        if levenshtein_ratio(normalised, banner) >= _BANNER_MATCH_THRESHOLD:
            return True
        if banner in normalised:
            remainder = normalised.replace(banner, " ").strip()
            if len(_LETTER_RE.findall(remainder)) < _MIN_CLAIM_LINE_CHARS:
                return True

    return False


def _noise_reason(
    line: ClassifiedLine,
    *,
    min_bangla_ratio: float,
    min_confidence: float,
    banners: list[str] | None = None,
) -> str | None:
    """Return why this line is chrome, or ``None`` when it is claim text."""
    text = line.text
    stripped = text.strip()

    if not stripped:
        return "empty"

    if line.confidence is not None and line.confidence < min_confidence:
        return "low_confidence"

    # Strip decorations before measuring, so a line that is *only* a handle,
    # URL or emoji collapses to nothing and is caught below.
    without_decoration = _EMOJI_RE.sub("", _HANDLE_RE.sub("", _URL_RE.sub("", stripped)))
    if not _LETTER_RE.search(without_decoration):
        if _URL_RE.search(stripped):
            return "url"
        if _HANDLE_RE.search(stripped):
            return "social_handle"
        if _PHONE_RE.match(stripped):
            return "phone_number"
        if _DATE_ONLY_RE.match(stripped):
            return "timestamp"
        return "no_letters"

    for reason, pattern in _NOISE_PATTERNS:
        if pattern.search(stripped):
            return reason

    if banners and _is_source_banner(stripped, banners):
        return "source_banner"

    if _DATE_ONLY_RE.match(stripped):
        return "timestamp"

    if line.bangla_ratio < min_bangla_ratio:
        return "not_bangla"

    if len(stripped) < _MIN_CLAIM_LINE_CHARS:
        return "too_short"

    return None
