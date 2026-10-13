from __future__ import annotations

import re
import unicodedata
from datetime import date

_BANGLA_DIGITS = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")

_MONTHS: dict[str, int] = {}
for _number, _names in enumerate(
    (
        ("জানুয়ারি", "জানুয়ারী", "january", "jan"),
        ("ফেব্রুয়ারি", "ফেব্রুয়ারী", "ফেব্রুযারি", "february", "feb"),
        ("মার্চ", "march", "mar"),
        ("এপ্রিল", "april", "apr"),
        ("মে", "may"),
        ("জুন", "june", "jun"),
        ("জুলাই", "july", "jul"),
        ("আগস্ট", "অগাস্ট", "আগষ্ট", "august", "aug"),
        ("সেপ্টেম্বর", "september", "sept", "sep"),
        ("অক্টোবর", "october", "oct"),
        ("নভেম্বর", "november", "nov"),
        ("ডিসেম্বর", "december", "dec"),
    ),
    start=1,
):
    for _name in _names:
        _MONTHS[unicodedata.normalize("NFC", _name)] = _number

_MONTH_ALT = "|".join(sorted((re.escape(m) for m in _MONTHS), key=len, reverse=True))
_SUFFIX = r"(?:st|nd|rd|th|লা|রা|ঠা|ই|শে)?"
_SEP = r"[\s,.\-/]*"

_DAY_MONTH_YEAR = re.compile(rf"(?<!\d)(\d{{1,2}}){_SUFFIX}{_SEP}({_MONTH_ALT})\.?{_SEP}(\d{{4}})(?!\d)", re.IGNORECASE)
_MONTH_DAY_YEAR = re.compile(rf"({_MONTH_ALT})\.?{_SEP}(\d{{1,2}}){_SUFFIX}{_SEP}(\d{{4}})(?!\d)", re.IGNORECASE)
_YEAR_MONTH_DAY = re.compile(r"(?<!\d)(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})(?!\d)")
_DAY_MONTH_YEAR_NUM = re.compile(r"(?<!\d)(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})(?!\d)")


def _safe(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def parse_card_date(raw: str | None) -> date | None:
    if not raw or not raw.strip():
        return None
    text = unicodedata.normalize("NFC", raw).translate(_BANGLA_DIGITS)

    found: set[date] = set()
    for m in _DAY_MONTH_YEAR.finditer(text):
        d = _safe(int(m.group(3)), _MONTHS[m.group(2).lower()], int(m.group(1)))
        if d:
            found.add(d)
    for m in _MONTH_DAY_YEAR.finditer(text):
        d = _safe(int(m.group(3)), _MONTHS[m.group(1).lower()], int(m.group(2)))
        if d:
            found.add(d)
    for m in _YEAR_MONTH_DAY.finditer(text):
        d = _safe(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        if d:
            found.add(d)
    for m in _DAY_MONTH_YEAR_NUM.finditer(text):
        d = _safe(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        if d:
            found.add(d)

    return found.pop() if len(found) == 1 else None
