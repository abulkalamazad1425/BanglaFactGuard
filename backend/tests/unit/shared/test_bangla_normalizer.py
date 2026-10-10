import pytest

from app.shared.utils.bangla_normalizer import (
    extract_canonical_domain,
    normalize_bangla_text,
    normalize_source_name,
)


def test_text_normalisation_removes_invisible_chars_and_unifies_punctuation_and_space():
    raw = "  ঢাকায়​  “বৃষ্টি”\t— ১০ জন।  "
    assert normalize_bangla_text(raw) == 'ঢাকায় "বৃষ্টি" - ১০ জন.'
    assert normalize_bangla_text(raw, normalize_digits=True) == 'ঢাকায় "বৃষ্টি" - 10 জন.'


@pytest.mark.parametrize("raw,expected", [
    ("প্রথম আলো", "prothomalo.com"),             # exact alias
    ("Prothom Alo", "prothomalo.com"),           # case-insensitive alias
    ("যুগান্তর অনলাইন", "jugantor.com"),          # alias prefix
    ("আজকের দৈনিক কালের কণ্ঠ", "kalerkantho.com"),  # alias contained
    ("www.example-news.com", "www.example-news.com"),  # bare domain kept
    ("অচেনা পত্রিকা", None),
    ("", None),
])
def test_source_name_resolution(raw, expected):
    assert normalize_source_name(raw) == expected


@pytest.mark.parametrize("raw,expected", [
    ("https://www.ThedailyStar.net/news/1", "thedailystar.net"),
    ("prothomalo.com/bangladesh", "prothomalo.com"),
    ("not a domain", None),
    ("", None),
])
def test_canonical_domain_extraction(raw, expected):
    assert extract_canonical_domain(raw) == expected
