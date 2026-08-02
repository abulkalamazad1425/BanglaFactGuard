"""
app/shared/utils/article_url_heuristics.py
============================================
Shared heuristics for deciding whether a discovered URL is *probably* a
news article, as opposed to a nav/category/tag/listing page.

## Why this exists

Both `SourceSearchStage` (S04) and `InternalSiteSearchClient` filter search
results down to "probable articles" before they're fetched. Historically
that filter was an all-or-nothing check against each source's hand-curated
`article_url_patterns` regex list: if a source had patterns configured and
none matched, the URL was rejected outright — even if it was a perfectly
good article link.

Bangla news sites redesign their URL schemes far more often than anyone
updates `verified_sources.article_url_patterns` for them. When that
happens, every candidate URL from every search provider gets filtered out,
the pipeline finds zero evidence, and the claim is wrongly resolved as
NOT_FOUND_IN_CLAIMED_SOURCE regardless of whether the story was actually
published. This module provides a structural fallback used when the
configured patterns don't match, so a stale pattern degrades matching
precision instead of breaking discovery entirely.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

_NON_ARTICLE_PATTERNS = [
    r"/tag/",
    r"/tags/",
    r"/author/",
    r"/category/",
    r"/categories/",
    r"/feed",
    r"\.rss$",
    r"\.xml$",
    r"\.atom$",
    r"/amp/$",
    r"\?s=",
    r"#comments$",
    r"news\.google\.com/search",
    r"google\.com/search",
    r"/search\?[^/]*$",
    r"/archive/?$",
    r"/archive/\d{4}-\d{2}-\d{2}/?$",
    r"/epaper",
]
NON_ARTICLE_URL_RE = re.compile("|".join(_NON_ARTICLE_PATTERNS), re.IGNORECASE)

_DATE_PATH_RE = re.compile(r"/\d{4}/\d{2}/\d{2}(/|$)")
_WORD_ID_TAIL_RE = re.compile(r"^[a-zA-Z]+-\d{3,}$")


def _segment_looks_like_id(segment: str) -> bool:
    if segment.isdigit():
        return len(segment) >= 4
    if _WORD_ID_TAIL_RE.match(segment):
        return True
    if len(segment) >= 8 and segment.isalnum() and any(c.isdigit() for c in segment):
        # Opaque alphanumeric slug (e.g. a short-hash CMS ID) rather than a
        # readable category word — category slugs are letters/hyphens only.
        return True
    return False


def looks_like_article_url(url: str) -> bool:
    """
    Structural fallback check: does this URL look like a specific article
    rather than a listing/category/tag/nav page?

    Looks for a `/YYYY/MM/DD/` date segment, or any path segment that reads
    as an opaque content ID (a run of 4+ digits, a `word-1234` slug, or an
    8+ character alphanumeric hash-like slug) — patterns shared by nearly
    every Bangla news CMS regardless of how the rest of the URL is shaped.
    """
    try:
        path = urlparse(url).path
    except Exception:
        return False

    if _DATE_PATH_RE.search(path):
        return True

    return any(_segment_looks_like_id(seg) for seg in path.split("/") if seg)


def is_probable_article(url: str, source_patterns: list[str] | None) -> bool:
    """
    Combined check used by search-result filtering.

    1. Always reject known non-article URL shapes (tags, feeds, search
       pages, etc.) — a source's custom patterns should never override this.
    2. If the source has custom `article_url_patterns` and one matches,
       accept immediately (high-confidence, curator-verified signal).
    3. Otherwise fall back to the structural heuristic above, so a stale or
       missing pattern list degrades gracefully instead of rejecting every
       candidate for that source.
    """
    if NON_ARTICLE_URL_RE.search(url):
        return False

    if source_patterns and any(re.search(pat, url) for pat in source_patterns):
        return True

    return looks_like_article_url(url)
