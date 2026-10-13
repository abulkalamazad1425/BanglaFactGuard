from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

try:
    from zoneinfo import ZoneInfo

    DHAKA_TZ = ZoneInfo("Asia/Dhaka")
except Exception:  # pragma: no cover
    DHAKA_TZ = timezone(timedelta(hours=6), "Asia/Dhaka")

_BANGLA_DIGITS = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")
_BANGLA_MONTHS = {
    "জানুয়ারি": "January", "ফেব্রুয়ারি": "February", "মার্চ": "March",
    "এপ্রিল": "April", "মে": "May", "জুন": "June", "জুলাই": "July",
    "আগস্ট": "August", "সেপ্টেম্বর": "September", "অক্টোবর": "October",
    "নভেম্বর": "November", "ডিসেম্বর": "December",
}
_ISO_RE = re.compile(
    r"^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2})(?::(\d{2})(?:\.\d+)?)?)?\s*(Z|[+-]\d{2}:?\d{2})?$"
)
_TEXT_FORMATS = ("%B %d, %Y", "%d %B %Y", "%b %d, %Y", "%d %b %Y", "%d/%m/%Y", "%d-%m-%Y")


@dataclass(frozen=True)
class ParsedPublication:
    local_date: date
    published_at: datetime | None
    has_time: bool
    tz_assumed: bool


def _offset(token: str | None) -> timezone | None:
    if not token:
        return None
    if token == "Z":
        return timezone.utc
    sign = 1 if token[0] == "+" else -1
    digits = token[1:].replace(":", "")
    return timezone(sign * timedelta(hours=int(digits[:2]), minutes=int(digits[2:4])))


def parse_publication(raw: str | None) -> ParsedPublication | None:
    if not raw:
        return None
    text = raw.strip().translate(_BANGLA_DIGITS)
    for bn, en in _BANGLA_MONTHS.items():
        text = text.replace(bn, en)

    m = _ISO_RE.match(text)
    if m:
        y, mo, d, hh, mi, ss, off = m.groups()
        try:
            if hh is None:
                return ParsedPublication(date(int(y), int(mo), int(d)), None, False, False)
            naive = datetime(int(y), int(mo), int(d), int(hh), int(mi), int(ss or 0))
        except ValueError:
            return None
        tz = _offset(off)
        if tz is None:
            aware, assumed = naive.replace(tzinfo=DHAKA_TZ), True
        else:
            aware, assumed = naive.replace(tzinfo=tz), False
        local = aware.astimezone(DHAKA_TZ)
        return ParsedPublication(local.date(), local, True, assumed)

    for fmt in _TEXT_FORMATS:
        try:
            return ParsedPublication(datetime.strptime(text, fmt).date(), None, False, False)
        except ValueError:
            continue
    return None
