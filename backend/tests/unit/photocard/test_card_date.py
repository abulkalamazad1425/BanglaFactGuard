"""A card's printed date is parsed, never guessed."""

from datetime import date

import pytest

from app.features.photocard.card_date import parse_card_date


@pytest.mark.parametrize("raw,expected", [
    ("০৫ অক্টোবর, ২০২৬", date(2026, 10, 5)),
    ("৫ই অক্টোবর ২০২৬", date(2026, 10, 5)),
    ("২১শে ফেব্রুয়ারি ২০২৪", date(2024, 2, 21)),
    ("প্রকাশ: ১লা মে, ২০২৫ | ১০:৩০", date(2025, 5, 1)),
    ("শনিবার, ০৪ অক্টোবর ২০২৫", date(2025, 10, 4)),
    ("October 5, 2026", date(2026, 10, 5)),
    ("5 Oct 2026", date(2026, 10, 5)),
    ("০৫/১০/২০২৬", date(2026, 10, 5)),  # day first
    ("05.10.2026", date(2026, 10, 5)),
    ("2026-10-05", date(2026, 10, 5)),
])
def test_complete_dates_parse(raw, expected):
    assert parse_card_date(raw) == expected


@pytest.mark.parametrize("raw", [
    None, "", "৫ অক্টোবর", "অক্টোবর ২০২৬", "২ ঘণ্টা আগে", "আজ", "০৫/১০/২৬", "২০ আশ্বিন ১৪৩৩",
    "31/02/2026", "০৫ অক্টোবর ২০২৬, আপডেট ০৬ অক্টোবর ২০২৬",
])
def test_incomplete_impossible_or_ambiguous_dates_are_not_guessed(raw):
    assert parse_card_date(raw) is None
