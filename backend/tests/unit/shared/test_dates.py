"""Publication dates are calendar days in Asia/Dhaka, with timezone provenance."""

from datetime import date

import pytest

from app.shared.utils.dates import parse_publication


def test_utc_timestamp_converts_to_the_dhaka_calendar_day():
    p = parse_publication("2026-03-15T21:30:00+00:00")
    assert p.local_date == date(2026, 3, 16) and p.has_time and p.tz_assumed is False
    assert p.published_at.utcoffset().total_seconds() == 6 * 3600
    assert parse_publication("2026-03-15T21:30:00Z").local_date == date(2026, 3, 16)


def test_offsetless_timestamp_assumes_dhaka_and_says_so():
    p = parse_publication("2026-03-15T21:30:00")
    assert p.local_date == date(2026, 3, 15) and p.tz_assumed is True


@pytest.mark.parametrize("raw,expected", [
    ("2026-03-15", date(2026, 3, 15)),
    ("১৫ মার্চ ২০২৬", date(2026, 3, 15)),     # Bangla digits and month
    ("March 15, 2026", date(2026, 3, 15)),
    ("15/03/2026", date(2026, 3, 15)),
    ("2026-02-30", None),                    # impossible day
    ("not a date", None),
    (None, None),
])
def test_date_forms(raw, expected):
    parsed = parse_publication(raw)
    assert (parsed.local_date if parsed else None) == expected
