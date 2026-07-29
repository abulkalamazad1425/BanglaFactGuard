
from __future__ import annotations

import re

from app.shared.utils.bangla_normalizer import normalize_bangla_digits






_ASCII_NUMBER_RE = re.compile(r"\b\d[\d,\.]*\d|\b\d\b")


_BANGLA_NUMBER_RE = re.compile(r"[০-৯][০-৯,\.]*[০-৯]|[০-৯]")


_BANGLA_WRITTEN_NUMBERS: dict[str, int] = {
    "এক": 1, "দুই": 2, "তিন": 3, "চার": 4, "পাঁচ": 5,
    "ছয়": 6, "সাত": 7, "আট": 8, "নয়": 9, "দশ": 10,
    "বিশ": 20, "ত্রিশ": 30, "চল্লিশ": 40, "পঞ্চাশ": 50,
    "ষাট": 60, "সত্তর": 70, "আশি": 80, "নব্বই": 90,
    "শ": 100, "শত": 100, "হাজার": 1000, "লাখ": 100_000,
    "লক্ষ": 100_000, "কোটি": 10_000_000,
}







def extract_numerals(text: str) -> list[str]:

    ascii_text = normalize_bangla_digits(text)

    numerals: list[str] = []


    for match in _ASCII_NUMBER_RE.finditer(ascii_text):
        raw = match.group()

        normalised = raw.replace(",", "")
        if normalised:
            numerals.append(normalised)

    return numerals


def extract_numerals_set(text: str) -> set[str]:
    return set(extract_numerals(text))


def compute_numerical_consistency(
    claim_text: str,
    article_text: str,
) -> float:
    claim_nums = extract_numerals_set(claim_text)
    article_nums = extract_numerals_set(article_text)

    if not claim_nums:

        return 1.0

    matched = len(claim_nums & article_nums)
    return matched / len(claim_nums)


def find_altered_numbers(
    claim_text: str,
    article_text: str,
) -> list[tuple[str, str | None]]:
    claim_nums = extract_numerals_set(claim_text)
    article_nums = extract_numerals_set(article_text)
    absent = claim_nums - article_nums

    result: list[tuple[str, str | None]] = []
    for num_str in sorted(absent):
        nearest = _find_nearest(num_str, article_nums)
        result.append((num_str, nearest))

    return result







def _find_nearest(target_str: str, candidates: set[str]) -> str | None:
    if not candidates:
        return None
    try:
        target_val = float(target_str.replace(",", ""))
    except ValueError:
        return None

    best: str | None = None
    best_diff = float("inf")
    for c in candidates:
        try:
            c_val = float(c.replace(",", ""))
            diff = abs(target_val - c_val)
            if diff < best_diff:
                best_diff = diff
                best = c
        except ValueError:
            continue
    return best
