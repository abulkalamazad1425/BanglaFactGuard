"""
app/utils/text_cleaner.py
==========================
Text cleaning utilities for post-extraction article content (Stage 6).

These functions are applied AFTER trafilatura/BS4 extracts raw text,
to remove residual noise that extraction does not eliminate:

1. **HTML entity decoding** — handles any remaining &amp;, &nbsp;, etc.
2. **Residual HTML tag removal** — strips any <tags> that slipped through.
3. **Advertisement/boilerplate pattern removal** — common Bangla news site
   footers ("সর্বস্বত্ব সংরক্ষিত", "আরও পড়ুন", cookie banners, etc.).
4. **Excessive whitespace normalisation** — collapses repeated blank lines.
5. **Minimum length enforcement** — returns None if cleaned text is below
   the minimum usable length threshold.

All functions are pure and idempotent.
"""

from __future__ import annotations

import html
import re

from app.core.config import get_settings

_SETTINGS = get_settings()

# ---------------------------------------------------------------------------
# Compiled regex patterns
# ---------------------------------------------------------------------------

# Residual HTML tags
_HTML_TAG_RE = re.compile(r"<[^>]+>", re.DOTALL)

# Excessive blank lines (3+ consecutive newlines → 2)
_EXCESS_BLANK_LINES_RE = re.compile(r"\n{3,}")

# Repeated whitespace within a line
_INLINE_WHITESPACE_RE = re.compile(r"[ \t]+")

# Bangla news site boilerplate patterns — common across major outlets
_BOILERPLATE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(p, re.IGNORECASE | re.UNICODE)
    for p in [
        r"সর্বস্বত্ব\s*সংরক্ষিত",          # "All rights reserved"
        r"আরও\s*পড়ুন[:\s]",                 # "Read more:"
        r"আরো\s*পড়ুন[:\s]",                 # Alternate spelling
        r"এই\s*বিষয়ে\s*আরও",               # "More on this topic"
        r"সংশ্লিষ্ট\s*খবর",                 # "Related news"
        r"সম্পর্কিত\s*খবর",                 # "Related articles"
        r"শেয়ার\s*করুন",                    # "Share this"
        r"মন্তব্য\s*করুন",                   # "Comment"
        r"ফেসবুকে\s*শেয়ার",                 # "Share on Facebook"
        r"টুইটারে\s*শেয়ার",                 # "Share on Twitter"
        r"প্রিন্ট\s*করুন",                   # "Print"
        r"ইমেইলে\s*পাঠান",                   # "Send by email"
        r"কুকি\s*নীতি",                      # "Cookie policy"
        r"গোপনীয়তা\s*নীতি",                 # "Privacy policy"
        r"বিজ্ঞাপন",                          # "Advertisement"
        r"(?:^|\n)\s*tags?\s*:",             # "Tags:" at line start
        r"(?:^|\n)\s*keywords?\s*:",         # "Keywords:" at line start
        r"(?:^|\n)\s*category\s*:",          # "Category:" at line start
        r"Subscribe\s+to\s+our\s+newsletter",
        r"Follow\s+us\s+on",
        r"Download\s+our\s+app",
        r"Copyright\s+©",
        r"All\s+rights\s+reserved",
    ]
]

# Patterns that indicate a line is pure metadata noise (short + no Bangla)
_METADATA_LINE_RE = re.compile(
    r"^[\s\d\|•·–\-:,./()[\]\"'A-Za-z@#%+]+$"
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def clean_extracted_text(
    text: str,
    *,
    remove_boilerplate: bool = True,
    min_length: int | None = None,
) -> str | None:
    """
    Clean raw extracted article text for downstream NLP processing.

    Applies the full cleaning pipeline:
    1. HTML entity decode
    2. Residual HTML tag removal
    3. Boilerplate pattern removal (optional)
    4. Whitespace normalisation
    5. Minimum length check

    Args:
        text:               Raw extracted text from trafilatura or BS4.
        remove_boilerplate: Whether to apply boilerplate pattern removal.
                            Set False in tests to avoid removing test fixtures.
        min_length:         Minimum character count for the result to be
                            considered valid. If None, uses settings default.

    Returns:
        Cleaned text string, or None if the result is below `min_length`.
    """
    if not text:
        return None

    _min = min_length if min_length is not None else _SETTINGS.search.min_body_length_chars

    # Step 1: HTML entity decode (&amp; → &, &nbsp; → space, etc.)
    text = html.unescape(text)

    # Step 2: Strip residual HTML tags
    text = _HTML_TAG_RE.sub(" ", text)

    # Step 3: Remove boilerplate patterns
    if remove_boilerplate:
        text = _remove_boilerplate(text)

    # Step 4: Normalise whitespace
    text = _normalise_whitespace(text)

    # Step 5: Minimum length check
    if len(text) < _min:
        return None

    return text


def clean_title(title: str | None) -> str | None:
    """
    Clean an extracted article title.

    Applies a lighter cleaning pass than body text:
    - HTML entity decode
    - Residual tag removal
    - Collapse to single line (remove newlines)
    - Strip leading/trailing whitespace

    Args:
        title: Raw extracted title string.

    Returns:
        Cleaned title or None if empty after cleaning.
    """
    if not title:
        return None

    text = html.unescape(title)
    text = _HTML_TAG_RE.sub(" ", text)
    text = text.replace("\n", " ").replace("\r", " ")
    text = _INLINE_WHITESPACE_RE.sub(" ", text).strip()
    return text if text else None


def truncate_for_nli(
    text: str,
    *,
    max_chars: int = 1500,
) -> str:
    """
    Truncate text to a safe length for NLI model input (Stage 9).

    NLI cross-encoders have a token limit (~512 tokens for DeBERTa).
    We truncate at the character level as a conservative pre-filter.
    Truncation is done at the nearest sentence boundary to avoid
    cutting mid-sentence.

    Args:
        text:      Input text to truncate.
        max_chars: Maximum character length (default 1500 ≈ ~512 BPE tokens
                   for Bangla/English mixed text).

    Returns:
        Truncated text, ending at a sentence boundary where possible.
    """
    if len(text) <= max_chars:
        return text

    # Find the last sentence boundary within max_chars
    truncated = text[:max_chars]
    # Try to end at a Bangla danda (।), period, or newline
    for boundary in ("।", ".", "\n"):
        last_idx = truncated.rfind(boundary)
        if last_idx > max_chars * 0.6:  # At least 60% of max_chars
            return truncated[: last_idx + 1].strip()

    return truncated.strip()


def extract_first_n_sentences(text: str, n: int = 5) -> str:
    """
    Extract the first N sentences from a text.

    Used for NLI input when only the lead of an article is needed
    (e.g. when the full body is very long).

    Args:
        text: Input text.
        n:    Number of sentences to extract.

    Returns:
        First N sentences joined into a single string.
    """
    # Split on Bangla danda, period, or exclamation/question mark
    sentence_end_re = re.compile(r"(?<=[।.!?])\s+")
    sentences = sentence_end_re.split(text.strip())
    selected = [s.strip() for s in sentences[:n] if s.strip()]
    return " ".join(selected)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _remove_boilerplate(text: str) -> str:
    """
    Remove boilerplate patterns from the text line-by-line and via regex.

    Args:
        text: Input text.

    Returns:
        Text with boilerplate removed.
    """
    # Apply compiled patterns to the full text
    for pattern in _BOILERPLATE_PATTERNS:
        text = pattern.sub("", text)

    # Filter out pure metadata lines
    cleaned_lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            cleaned_lines.append("")
            continue
        # Skip lines that are clearly metadata noise (no Bangla characters,
        # very short, only contains punctuation/numbers/Latin)
        if len(stripped) < 8 and _METADATA_LINE_RE.match(stripped):
            continue
        cleaned_lines.append(line)

    return "\n".join(cleaned_lines)


def _normalise_whitespace(text: str) -> str:
    """
    Collapse excessive blank lines and inline whitespace.

    Args:
        text: Input text.

    Returns:
        Whitespace-normalised text.
    """
    # Collapse inline whitespace (spaces/tabs) per line
    lines = [_INLINE_WHITESPACE_RE.sub(" ", line) for line in text.splitlines()]
    text = "\n".join(lines)
    # Collapse 3+ consecutive blank lines to at most 2
    text = _EXCESS_BLANK_LINES_RE.sub("\n\n", text)
    return text.strip()
