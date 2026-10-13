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
        return True
    return False


def looks_like_article_url(url: str) -> bool:
    try:
        path = urlparse(url).path
    except Exception:
        return False

    if _DATE_PATH_RE.search(path):
        return True

    return any(_segment_looks_like_id(seg) for seg in path.split("/") if seg)


def is_probable_article(url: str, source_patterns: list[str] | None) -> bool:
    if NON_ARTICLE_URL_RE.search(url):
        return False

    if source_patterns and any(re.search(pat, url) for pat in source_patterns):
        return True

    return looks_like_article_url(url)
