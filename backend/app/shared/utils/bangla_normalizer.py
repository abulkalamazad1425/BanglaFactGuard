
from __future__ import annotations

import re
import unicodedata

from app.core.constants import KNOWN_SOURCE_ALIASES






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


_ZERO_WIDTH_CHARS_RE = re.compile(
    r"[\u200B\u200C\u200D\u200E\u200F\uFEFF\u00AD]"
)


_MULTI_WHITESPACE_RE = re.compile(r"\s+")


_BANGLA_PUNCT_MAP: dict[str, str] = {
    "।": ".",
    "॥": ".",
    "\u201C": '"',
    "\u201D": '"',
    "\u2018": "'",
    "\u2019": "'",
    "\u2014": "-",
    "\u2013": "-",
    "\u2026": "...",
}
_BANGLA_PUNCT_TABLE = str.maketrans(_BANGLA_PUNCT_MAP)






def normalize_unicode(text: str) -> str:

    text = unicodedata.normalize("NFC", text)

    text = _ZERO_WIDTH_CHARS_RE.sub("", text)
    return text


def normalize_whitespace(text: str) -> str:
    return _MULTI_WHITESPACE_RE.sub(" ", text).strip()


def normalize_punctuation(text: str) -> str:
    return text.translate(_BANGLA_PUNCT_TABLE)


def normalize_bangla_digits(text: str) -> str:
    return text.translate(_BANGLA_DIGIT_TABLE)


def normalize_bangla_text(text: str, *, normalize_digits: bool = False) -> str:
    text = normalize_unicode(text)
    text = normalize_punctuation(text)
    if normalize_digits:
        text = normalize_bangla_digits(text)
    text = normalize_whitespace(text)
    return text







def normalize_source_name(raw_source: str) -> str | None:
    if not raw_source:
        return None


    stripped = raw_source.strip()
    lowered = stripped.lower()


    if lowered in KNOWN_SOURCE_ALIASES:
        return KNOWN_SOURCE_ALIASES[lowered]


    if stripped in KNOWN_SOURCE_ALIASES:
        return KNOWN_SOURCE_ALIASES[stripped]


    for alias, domain in KNOWN_SOURCE_ALIASES.items():
        if lowered.startswith(alias.lower()):
            return domain


    for alias, domain in KNOWN_SOURCE_ALIASES.items():
        alias_lower = alias.lower()
        if alias_lower and alias_lower in lowered:
            return domain


    if _looks_like_domain(lowered):
        return lowered

    return None


def _looks_like_domain(text: str) -> bool:

    domain_re = re.compile(
        r"^(?:www\.)?(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}$"
    )
    return bool(domain_re.match(text.strip()))


def extract_canonical_domain(url_or_domain: str) -> str | None:
    from urllib.parse import urlparse

    if not url_or_domain:
        return None

    try:

        if not url_or_domain.startswith(("http://", "https://")):
            url_or_domain = "https://" + url_or_domain

        parsed = urlparse(url_or_domain)
        hostname = parsed.hostname or ""


        if hostname.startswith("www."):
            hostname = hostname[4:]

        return hostname.lower() if hostname else None
    except Exception:
        return None
