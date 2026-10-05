
"""Deterministic claim extraction from photo-card OCR text - the FALLBACK path.

Used only after every Gemini image-extraction attempt failed
(`claim_extraction.py`): EasyOCR reads the card, then this module removes
card chrome (social calls to action, bylines, credits, timestamps, handles,
URLs, outlet banners) and segments what remains into a headline. It also
returns the first date-looking fragment exactly as OCR read it (display
only; never compared with anything).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from Levenshtein import ratio as levenshtein_ratio
from app.shared.utils.bangla_normalizer import normalize_unicode, normalize_whitespace
_LETTER_RE = re.compile(r"[^\W\d_]", re.UNICODE)
_MATCH_PUNCT_RE = re.compile(r"[^\w\sঀ-৿]", re.UNICODE)
# Conservative prose boundaries: do not split a headline at ! or ?.
# Photo cards often use those between headline clauses.
_SENTENCE_END_RE = re.compile(r"(?<=[।\.])\s+")
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
# Exact category labels; never remove these words inside a claim.
_SECTION_NAMES = (
    "বিনোদন", "জাতীয়", "জাতীয়", "আন্তর্জাতিক", "রাজনীতি", "খেলা",
    "খেলাধুলা", "ক্রীড়া", "ক্রীড়া", "অর্থনীতি", "বাংলাদেশ", "বিশ্ব",
    "শিক্ষা", "প্রযুক্তি", "জীবনযাপন", "স্বাস্থ্য", "মতামত", "চাকরি",
    "ধর্ম", "বাণিজ্য", "রাজধানী", "সারাদেশ", "সারা দেশ",
)
_SECTION_RE = re.compile(
    r"^(?:" + "|".join(map(re.escape, _SECTION_NAMES)) + r")(?=$|[\s|:：•·—–-])"
)
_HEADER_DATE_RE = re.compile(
    rf"^(?:[০-৯0-9]{{1,2}}\s+(?:{_BANGLA_MONTHS})\s+[০-৯0-9]{{4}}"
    r"|[০-৯0-9]{1,2}[/.-][০-৯0-9]{1,2}[/.-][০-৯0-9]{4}"
    r"|[০-৯0-9]{4}[/.-][০-৯0-9]{1,2}[/.-][০-৯0-9]{1,2})"
    r"(?=$|[\s|:：•·—–-])"
)
_HEADER_SEPARATOR = " \t|:：•·—–-"
_OCR_MIXED_TOKEN_RE = re.compile(
    r"[ঀ-৿][0-9০-৯\[\]{}|][ঀ-৿0-9০-৯\[\]{}|]*"
    r"|[0-9০-৯\[\]{}|]+[ঀ-৿]"
)

# OCR often reads the footer wordmark/URL as Bengali letters interrupted by
# vertical bars. These are structural rules, not guessed outlet spellings.
_BROKEN_WORDMARK_RE = re.compile(r"[ঀ-৿][|\[\]{}][ঀ-৿]|[|\[\]{}][ঀ-৿]")
_STRAY_ASCII_MARKER_RE = re.compile(r"(?<!\S)[0-9]{1,3}[)\]}](?=\s|$)")
_FOOTER_REASONS = {
    "url", "social_handle", "source_banner", "copyright", "social_cta",
}


def _looks_like_broken_wordmark(text: str) -> bool:
    compact = re.sub(r"\s+", "", text)
    structural = sum(char in "|[]{}" for char in compact)
    return (
        len(text.split()) <= 2
        and structural >= 2
        and structural / max(len(compact), 1) >= 0.15
        and bool(_BROKEN_WORDMARK_RE.search(compact))
    )


def _clean_inline_artifacts(text: str, *, template_region: bool) -> str:
    """Clean visible chrome without deleting meaningful claim numbers."""
    text = _URL_RE.sub(" ", text)
    text = _HANDLE_RE.sub(" ", text)
    text = _EMOJI_RE.sub(" ", text)
    if template_region:
        # Only isolated ASCII '9)' style OCR fragments inside this template.
        # Never remove ৫, ১৩৮, ৫২, percentages, decimals or years.
        original = text
        text = _STRAY_ASCII_MARKER_RE.sub(
            lambda match: (
                " "
                if re.search(r"[ঀ-৿]", original[:match.start()])
                and re.search(r"[ঀ-৿]", original[match.end():])
                else match.group()
            ),
            text,
        )
    return normalize_whitespace(text)


def _template_header_index(lines: list[ClassifiedLine]) -> int | None:
    """Find a category + full-date header, including two separate OCR lines.

    No source identity or dates are invented. This detects the layout family,
    not the truth/source of the image. Raw OCR remains the provenance input.
    """
    previous_category = False
    for index, line in enumerate(lines):
        raw = normalize_whitespace(normalize_unicode(line.original_text or line.text))
        _, reason = _strip_card_header(raw)
        if reason == "section_date_header":
            return index
        if previous_category and reason == "timestamp":
            return index
        previous_category = reason == "section_label"
    return None


def _select_template_region(lines: list[ClassifiedLine]) -> bool:
    """Keep the headline block between the header and footer.

    This family has one headline block and no supporting article body. Join
    every surviving line there, even short words or lines ending in !/?.
    Other layouts retain the generic segmentation path.
    """
    header = _template_header_index(lines)
    if header is None or not any(not line.is_noise for line in lines[header:]):
        return False
    for line in lines[:header]:
        line.is_noise = True
        line.noise_reason = "before_headline_header"
    started = False
    footer = False
    for line in lines[header:]:
        if footer:
            if not line.is_noise:
                line.is_noise = True
                line.noise_reason = "after_headline_footer"
            continue
        if line.is_noise:
            if started and (
                line.noise_reason in _FOOTER_REASONS
                or _looks_like_broken_wordmark(line.text)
            ):
                footer = True
            continue
        cleaned = _clean_inline_artifacts(line.text, template_region=True)
        if not _LETTER_RE.search(cleaned):
            line.is_noise = True
            line.noise_reason = "inline_ocr_artifact"
            continue
        line.text = cleaned
        line.bangla_ratio = bangla_ratio(cleaned)
        started = True
    return True
def _strip_card_header(text: str) -> tuple[str, str | None]:
    """Remove category/date headers; retain dates that form part of a claim."""
    candidate = text.strip(_HEADER_SEPARATOR)
    category = _SECTION_RE.match(candidate)
    if category:
        remainder = candidate[category.end():].strip(_HEADER_SEPARATOR)
        if not remainder:
            return "", "section_label"
        date = _HEADER_DATE_RE.match(remainder)
        if date:
            return remainder[date.end():].strip(_HEADER_SEPARATOR), "section_date_header"
        # 'বিনোদন জগতে ...' is a headline, not a category label.
    date = _HEADER_DATE_RE.match(candidate)
    if date and not candidate[date.end():].strip(_HEADER_SEPARATOR):
        return "", "timestamp"
    return text, None
def _is_garbled_ocr(text: str) -> bool:
    """Reject structurally corrupted OCR, without guessing names or spelling.
    Corrupted tokens must dominate and digits/brackets must occupy >=20%.
    Ordinary numbers, unusual Bengali names and intact words survive.
    This deliberately does not identify every possible garbled footer.
    """
    if _looks_like_broken_wordmark(text):
        return True
    tokens = text.split()
    if not tokens:
        return False
    corrupted = sum(bool(_OCR_MIXED_TOKEN_RE.search(token)) for token in tokens)
    junk = sum(char.isdigit() or char in "[]{}|" for char in text)
    return corrupted / len(tokens) >= 0.5 and junk / len(text) >= 0.20
def _clean_headline(text: str) -> str:
    # Remove decorative trailing ellipses; preserve meaningful ! and ?.
    return re.sub(r"(?:\.{2,}|…+)\s*$", "", text).strip()
@dataclass
class ClassifiedLine:
    """One OCR line with the verdict on whether it belongs to the claim."""
    text: str
    confidence: float | None = None
    bangla_ratio: float = 0.0
    is_noise: bool = False
    noise_reason: str | None = None
    original_text: str | None = None
@dataclass
class ExtractedClaim:
    """The claim recovered from a photo card, for headline-only verification."""
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
    raw_lines: list[tuple[str, float | None]] | str,
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
    if isinstance(raw_lines, str):
        raw_lines = [(raw_lines, None)]
    # Some OCR clients return a single multiline record.
    split_lines = [
        (part, confidence)
        for raw_text, confidence in raw_lines
        for part in raw_text.splitlines()
    ]
    for raw_text, confidence in split_lines:
        # Preserve original punctuation; downstream S01 handles normalization.
        text = normalize_whitespace(normalize_unicode(raw_text))
        if not text:
            continue
        line = ClassifiedLine(
            text=text,
            confidence=confidence,
            bangla_ratio=bangla_ratio(text),
            original_text=raw_text,
        )
        if confidence is not None and confidence < min_confidence:
            line.is_noise = True
            line.noise_reason = "low_confidence"
            classified.append(line)
            continue
        cleaned, header_reason = _strip_card_header(text)
        if header_reason and not cleaned:
            line.is_noise = True
            line.noise_reason = header_reason
            classified.append(line)
            continue
        line.text = cleaned
        line.bangla_ratio = bangla_ratio(cleaned)
        reason = _noise_reason(
            line,
            min_bangla_ratio=min_bangla_ratio,
            min_confidence=min_confidence,
            banners=banners,
        )
        if reason:
            line.is_noise = True
            line.noise_reason = reason
        else:
            line.text = _clean_inline_artifacts(line.text, template_region=False)
            line.bangla_ratio = bangla_ratio(line.text)
        classified.append(line)
    return classified
def extract_claim(
    raw_lines: list[tuple[str, float | None]] | str,
    *,
    min_bangla_ratio: float = 0.45,
    min_confidence: float = 0.30,
    source_names: list[str] | None = None,
) -> ExtractedClaim:
    """Extract a headline and body from raw OCR lines.
    Category/date cards use the complete block between the metadata header
    and footer. Other layouts use conservative text segmentation. No font
    size or bounding-box information is available through this API.
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
    template_region = _select_template_region(lines)
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
    if template_region:
        headline, body = " ".join(kept), ""
    else:
        headline, body = _segment(kept)
    headline = _clean_headline(headline)
    if template_region and len(headline) > _MAX_HEADLINE_CHARS:
        warnings.append(
            "The header-to-footer block is too long for a reliable headline; "
            "extraction is unavailable rather than silently truncated."
        )
        headline = ""
    if len(headline) < _MIN_CLAIM_LINE_CHARS:
        warnings.append(
            "The detected headline is very short and may be incomplete."
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
        # Append the final wrapped headline line before checking its punctuation.
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
    # ! and ? frequently separate two clauses within one photo-card headline.
    # They are not reliable headline/body boundaries without OCR geometry.
    return text.rstrip().endswith(("।", ".", "…"))
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
        # A news claim ABOUT advertising, likes, credits or an outlet is not
        # itself card chrome. Avoid substring matches inside real headlines.
        if reason in {"advert", "engagement"}:
            matched = pattern.fullmatch(stripped)
        else:
            matched = pattern.match(stripped)
        if matched:
            return reason
    if banners and _is_source_banner(stripped, banners):
        return "source_banner"
    if _DATE_ONLY_RE.match(stripped):
        return "timestamp"
    if _is_garbled_ocr(stripped):
        return "garbled_ocr"
    if line.bangla_ratio < min_bangla_ratio:
        return "not_bangla"
    # Headline wrapping can leave a meaningful one-word line ('আলোচনা',
    # 'গল্প', 'আজ'). Judge fragment length after assembling the headline.
    if len(_LETTER_RE.findall(stripped)) < 2:
        return "too_short"
    return None


_DATE_IN_LINE_RE = re.compile(
    rf"[\d০-৯]{{1,2}}\s*(?:{_BANGLA_MONTHS})[\s,]*[\d০-৯]{{2,4}}"
    rf"|(?:{_BANGLA_MONTHS})\s*[\d০-৯]{{1,2}}[\s,]+[\d০-৯]{{4}}"
    r"|[\d০-৯]{1,2}[./-][\d০-৯]{1,2}[./-][\d০-৯]{2,4}",
    re.IGNORECASE,
)


def detect_date_text(raw_lines: list[tuple[str, float | None]] | str) -> str | None:
    """The first date-looking fragment, exactly as OCR read it (no format
    change). Display-only metadata for the fallback path."""
    lines = [raw_lines] if isinstance(raw_lines, str) else [t for t, _ in raw_lines]
    for text in lines:
        match = _DATE_IN_LINE_RE.search(text or "")
        if match:
            return match.group(0).strip()
    return None
