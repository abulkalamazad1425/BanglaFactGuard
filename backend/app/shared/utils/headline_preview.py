"""Short headline previews for notification text."""

from __future__ import annotations

import unicodedata

PREVIEW_WORDS = 5


def headline_preview(headline: str | None, words: int = PREVIEW_WORDS) -> str:
    """The first `words` whitespace-separated words of `headline`, followed by
    "..." only when more words exist. Works for Bangla and English alike:
    `str.split()` splits on every Unicode whitespace character (including
    no-break spaces) and collapses runs of it. Returns "" for a blank headline.
    """
    tokens = unicodedata.normalize("NFC", headline or "").split()
    preview = " ".join(tokens[:words])
    return f"{preview}..." if len(tokens) > words else preview
