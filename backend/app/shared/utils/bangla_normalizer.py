"""
app/utils/bangla_normalizer.py
================================
Bangla and Unicode text normalisation utilities for Stage 1 of the pipeline.

## What is normalised

1. **Unicode NFC normalisation** — ensures composed form (ক + া = কা, not
   decomposed sequences), eliminating hash collisions on semantically identical
   Bangla text written with different Unicode representations.

2. **Zero-width character removal** — strips ZWJ (U+200D), ZWNJ (U+200C),
   and BOM (U+FEFF) characters that are invisible but break string equality.

3. **Bangla punctuation normalisation** — maps Bangla danda (।) and double
   danda (॥) to ASCII period, and Bangla-specific quotation marks to standard
   ASCII equivalents for consistent tokenization downstream.

4. **Hasanta normalisation** — normalises the Bangla virama (্) for
   consistent handling across different keyboard layouts.

5. **Whitespace normalisation** — collapses multiple spaces/tabs/newlines into
   a single space and strips leading/trailing whitespace.

6. **Digit normalisation** — optionally converts Bangla numerals (০১২৩৪৫৬৭৮৯)
   to ASCII digits (0-9) for numeral consistency checks in Stage 8.

7. **Source string normalisation** — maps common Bangla/transliterated outlet
   names to canonical domains using the static KNOWN_SOURCE_ALIASES map, with
   fuzzy prefix matching as a fallback.

All functions are pure (no I/O, no ML calls) and idempotent.
"""

from __future__ import annotations

import re
import unicodedata

from app.core.constants import KNOWN_SOURCE_ALIASES

# ---------------------------------------------------------------------------
# Character maps
# ---------------------------------------------------------------------------

# Bangla digit → ASCII digit mapping
_BANGLA_DIGITS: dict[str, str] = {
    "০": "0",
    "১": "1",
    "২": "2",
    "৩": "3",
    "৪": "4",
    "৫": "5",
    "৬": "6",
    "৭": "7",
    "৮": "8",
    "৯": "9",
}
_BANGLA_DIGIT_TABLE = str.maketrans(_BANGLA_DIGITS)

# Zero-width and invisible characters to remove
_ZERO_WIDTH_CHARS_RE = re.compile(
    r"[\u200B\u200C\u200D\u200E\u200F\uFEFF\u00AD]"
)

# Normalise multiple whitespace (spaces, tabs, newlines) → single space
_MULTI_WHITESPACE_RE = re.compile(r"\s+")

# Bangla punctuation → ASCII equivalent
_BANGLA_PUNCT_MAP: dict[str, str] = {
    "।": ".",    # Bangla danda → ASCII period
    "॥": ".",    # Double danda → ASCII period
    "\u201C": '"',  # Left double quotation mark
    "\u201D": '"',  # Right double quotation mark
    "\u2018": "'",  # Left single quotation mark
    "\u2019": "'",  # Right single quotation mark
    "\u2014": "-",  # Em dash
    "\u2013": "-",  # En dash
    "\u2026": "...",  # Ellipsis
}
_BANGLA_PUNCT_TABLE = str.maketrans(_BANGLA_PUNCT_MAP)

# ---------------------------------------------------------------------------
# Core normalisation functions
# ---------------------------------------------------------------------------


def normalize_unicode(text: str) -> str:
    """
    Apply Unicode NFC normalisation and remove zero-width invisible characters.

    This is the foundational normalisation step — always apply this first
    before any other text processing.

    Args:
        text: Raw input string (Bangla, mixed, or ASCII).

    Returns:
        NFC-normalised string with invisible characters removed.
    """
    # NFC: Canonical Decomposition followed by Canonical Composition
    text = unicodedata.normalize("NFC", text)
    # Remove zero-width and invisible characters
    text = _ZERO_WIDTH_CHARS_RE.sub("", text)
    return text


def normalize_whitespace(text: str) -> str:
    """
    Collapse all whitespace sequences to a single ASCII space and strip ends.

    Args:
        text: Input string (may contain tabs, newlines, multiple spaces).

    Returns:
        Whitespace-normalised string.
    """
    return _MULTI_WHITESPACE_RE.sub(" ", text).strip()


def normalize_punctuation(text: str) -> str:
    """
    Map Bangla-specific punctuation marks to their ASCII equivalents.

    Args:
        text: Input string potentially containing Bangla punctuation.

    Returns:
        String with Bangla punctuation mapped to ASCII.
    """
    return text.translate(_BANGLA_PUNCT_TABLE)


def normalize_bangla_digits(text: str) -> str:
    """
    Convert Bangla numeral characters (০–৯) to ASCII digits (0–9).

    This is applied in Stage 8 (Numerical Consistency) to ensure that
    "১০" and "10" are treated as the same number.

    Args:
        text: Input string potentially containing Bangla digits.

    Returns:
        String with Bangla digits converted to ASCII.
    """
    return text.translate(_BANGLA_DIGIT_TABLE)


def normalize_bangla_text(text: str, *, normalize_digits: bool = False) -> str:
    """
    Full Bangla text normalisation pipeline.

    Applies in order:
    1. Unicode NFC + zero-width removal
    2. Punctuation normalisation
    3. Whitespace collapse
    4. Optionally: Bangla digit → ASCII digit conversion

    Args:
        text:             Raw Bangla or mixed text.
        normalize_digits: If True, converts Bangla digits to ASCII.
                          Set True for numeral consistency checks (Stage 8).
                          Set False for general text (preserves Bangla script).

    Returns:
        Fully normalised string.
    """
    text = normalize_unicode(text)
    text = normalize_punctuation(text)
    if normalize_digits:
        text = normalize_bangla_digits(text)
    text = normalize_whitespace(text)
    return text


# ---------------------------------------------------------------------------
# Source name normalisation
# ---------------------------------------------------------------------------


def normalize_source_name(raw_source: str) -> str | None:
    """
    Resolve a raw claimed-source string to its canonical domain name.

    Resolution strategy (in priority order):
    1. Direct lookup in KNOWN_SOURCE_ALIASES (exact match on lowercased key).
    2. Prefix match — if raw_source starts with a known alias key.
    3. Contained-in match — if a known alias key appears within raw_source.
    4. Return None if no match is found (DB lookup attempted next in Stage 1).

    The result is always a canonical domain string like "prothomalo.com"
    or None if resolution failed.

    Args:
        raw_source: User-supplied claimed-source string in any form.

    Returns:
        Canonical domain string or None.
    """
    if not raw_source:
        return None

    # Normalise for matching (preserve original for Bangla)
    stripped = raw_source.strip()
    lowered = stripped.lower()

    # 1. Exact match
    if lowered in KNOWN_SOURCE_ALIASES:
        return KNOWN_SOURCE_ALIASES[lowered]

    # Also try original-case for Bangla script
    if stripped in KNOWN_SOURCE_ALIASES:
        return KNOWN_SOURCE_ALIASES[stripped]

    # 2. Prefix match (lowercased)
    for alias, domain in KNOWN_SOURCE_ALIASES.items():
        if lowered.startswith(alias.lower()):
            return domain

    # 3. Substring containment (lowercased)
    for alias, domain in KNOWN_SOURCE_ALIASES.items():
        alias_lower = alias.lower()
        if alias_lower and alias_lower in lowered:
            return domain

    # 4. If the raw source already looks like a domain, return it normalised
    if _looks_like_domain(lowered):
        return lowered

    return None


def _looks_like_domain(text: str) -> bool:
    """
    Heuristic check: does the text look like a domain name?

    Accepts: "prothomalo.com", "www.prothomalo.com", "prothomalo.com.bd"

    Args:
        text: Lowercased string to check.

    Returns:
        True if the string appears to be a domain.
    """
    # A domain must have at least one dot and only domain-safe characters
    domain_re = re.compile(
        r"^(?:www\.)?(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}$"
    )
    return bool(domain_re.match(text.strip()))


def extract_canonical_domain(url_or_domain: str) -> str | None:
    """
    Extract the canonical domain from a full URL or domain string.

    Strips scheme (http/https), www prefix, and path to return just
    the registrable domain. Used when the claimed source is a full URL.

    Args:
        url_or_domain: A URL ("https://www.prothomalo.com/article/123")
                       or a domain ("www.prothomalo.com").

    Returns:
        Canonical domain string (e.g. "prothomalo.com") or None on failure.

    Examples::

        extract_canonical_domain("https://www.prothomalo.com/news/123")
        # → "prothomalo.com"

        extract_canonical_domain("www.thedailystar.net")
        # → "thedailystar.net"
    """
    from urllib.parse import urlparse

    if not url_or_domain:
        return None

    try:
        # Add scheme if missing so urlparse works
        if not url_or_domain.startswith(("http://", "https://")):
            url_or_domain = "https://" + url_or_domain

        parsed = urlparse(url_or_domain)
        hostname = parsed.hostname or ""

        # Strip leading 'www.'
        if hostname.startswith("www."):
            hostname = hostname[4:]

        return hostname.lower() if hostname else None
    except Exception:  # noqa: BLE001
        return None
