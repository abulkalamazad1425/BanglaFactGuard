from __future__ import annotations

import unicodedata

PREVIEW_WORDS = 5


def headline_preview(headline: str | None, words: int = PREVIEW_WORDS) -> str:
    tokens = unicodedata.normalize("NFC", headline or "").split()
    preview = " ".join(tokens[:words])
    return f"{preview}..." if len(tokens) > words else preview
