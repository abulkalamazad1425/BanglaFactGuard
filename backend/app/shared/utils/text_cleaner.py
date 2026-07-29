
from __future__ import annotations

import html
import re

from app.core.config import get_settings

_SETTINGS = get_settings()






_HTML_TAG_RE = re.compile(r"<[^>]+>", re.DOTALL)


_EXCESS_BLANK_LINES_RE = re.compile(r"\n{3,}")


_INLINE_WHITESPACE_RE = re.compile(r"[ \t]+")


_BOILERPLATE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(p, re.IGNORECASE | re.UNICODE)
    for p in [
        r"সর্বস্বত্ব\s*সংরক্ষিত",
        r"আরও\s*পড়ুন[:\s]",
        r"আরো\s*পড়ুন[:\s]",
        r"এই\s*বিষয়ে\s*আরও",
        r"সংশ্লিষ্ট\s*খবর",
        r"সম্পর্কিত\s*খবর",
        r"শেয়ার\s*করুন",
        r"মন্তব্য\s*করুন",
        r"ফেসবুকে\s*শেয়ার",
        r"টুইটারে\s*শেয়ার",
        r"প্রিন্ট\s*করুন",
        r"ইমেইলে\s*পাঠান",
        r"কুকি\s*নীতি",
        r"গোপনীয়তা\s*নীতি",
        r"বিজ্ঞাপন",
        r"(?:^|\n)\s*tags?\s*:",
        r"(?:^|\n)\s*keywords?\s*:",
        r"(?:^|\n)\s*category\s*:",
        r"Subscribe\s+to\s+our\s+newsletter",
        r"Follow\s+us\s+on",
        r"Download\s+our\s+app",
        r"Copyright\s+©",
        r"All\s+rights\s+reserved",
    ]
]


_METADATA_LINE_RE = re.compile(
    r"^[\s\d\|•·–\-:,./()[\]\"'A-Za-z@#%+]+$"
)







def clean_extracted_text(
    text: str,
    *,
    remove_boilerplate: bool = True,
    min_length: int | None = None,
) -> str | None:
    if not text:
        return None

    _min = min_length if min_length is not None else _SETTINGS.search.min_body_length_chars


    text = html.unescape(text)


    text = _HTML_TAG_RE.sub(" ", text)


    if remove_boilerplate:
        text = _remove_boilerplate(text)


    text = _normalise_whitespace(text)


    if len(text) < _min:
        return None

    return text


def clean_title(title: str | None) -> str | None:
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
    if len(text) <= max_chars:
        return text


    truncated = text[:max_chars]

    for boundary in ("।", ".", "\n"):
        last_idx = truncated.rfind(boundary)
        if last_idx > max_chars * 0.6:
            return truncated[: last_idx + 1].strip()

    return truncated.strip()


def extract_first_n_sentences(text: str, n: int = 5) -> str:

    sentence_end_re = re.compile(r"(?<=[।.!?])\s+")
    sentences = sentence_end_re.split(text.strip())
    selected = [s.strip() for s in sentences[:n] if s.strip()]
    return " ".join(selected)







def _remove_boilerplate(text: str) -> str:

    for pattern in _BOILERPLATE_PATTERNS:
        text = pattern.sub("", text)


    cleaned_lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            cleaned_lines.append("")
            continue


        if len(stripped) < 8 and _METADATA_LINE_RE.match(stripped):
            continue
        cleaned_lines.append(line)

    return "\n".join(cleaned_lines)


def _normalise_whitespace(text: str) -> str:

    lines = [_INLINE_WHITESPACE_RE.sub(" ", line) for line in text.splitlines()]
    text = "\n".join(lines)

    text = _EXCESS_BLANK_LINES_RE.sub("\n\n", text)
    return text.strip()
