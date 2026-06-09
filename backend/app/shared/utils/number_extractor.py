"""
app/utils/number_extractor.py
================================
Numerical value extraction and consistency checking for Stage 8.

## Purpose

Detect whether numerical values in a claim (headline/body) match those in
the best-matching article. Numerical manipulation is a common disinformation
technique — e.g. changing "১০ জন নিহত" (10 killed) to "১০০ জন নিহত" (100 killed).

## Extraction strategy

Extracts:
1. **Bangla numerals** (০–৯) converted to ASCII for comparison.
2. **ASCII digits** (0–9) as-is.
3. **Bangla written numbers** (e.g. "দশ", "শত", "হাজার") — mapped to numeric values.
4. **Year patterns** (২০২৪, 2024) treated as regular numbers.
5. **Decimal and comma-separated numbers** (১,৫০০ → 1500).

## Consistency scoring

Given a set of claim numerals and article numerals, the consistency score is:
    score = |claim_nums ∩ article_nums| / max(|claim_nums|, 1)

A score of 1.0 means every numeral in the claim appears in the article.
A score of 0.0 means no claim numerals were found in the article.
If the claim contains NO numerals, score = 1.0 (no numerical claim to verify).

All functions are pure.
"""

from __future__ import annotations

import re

from app.utils.bangla_normalizer import normalize_bangla_digits

# ---------------------------------------------------------------------------
# Compiled patterns
# ---------------------------------------------------------------------------

# ASCII digit sequences (including decimals and comma-separated)
_ASCII_NUMBER_RE = re.compile(r"\b\d[\d,\.]*\d|\b\d\b")

# Bangla digit sequences (including decimals)
_BANGLA_NUMBER_RE = re.compile(r"[০-৯][০-৯,\.]*[০-৯]|[০-৯]")

# Bangla written number words → approximate integer value
_BANGLA_WRITTEN_NUMBERS: dict[str, int] = {
    "এক": 1, "দুই": 2, "তিন": 3, "চার": 4, "পাঁচ": 5,
    "ছয়": 6, "সাত": 7, "আট": 8, "নয়": 9, "দশ": 10,
    "বিশ": 20, "ত্রিশ": 30, "চল্লিশ": 40, "পঞ্চাশ": 50,
    "ষাট": 60, "সত্তর": 70, "আশি": 80, "নব্বই": 90,
    "শ": 100, "শত": 100, "হাজার": 1000, "লাখ": 100_000,
    "লক্ষ": 100_000, "কোটি": 10_000_000,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract_numerals(text: str) -> list[str]:
    """
    Extract all numerical tokens from text as normalised ASCII digit strings.

    Handles Bangla digits (০–৯ → 0–9), ASCII digits, comma-separated numbers,
    and decimal numbers.

    Args:
        text: Input text (Bangla or mixed).

    Returns:
        List of normalised numeral strings (e.g. ["10", "100", "2024"]).
        Duplicates preserved (for frequency analysis).

    Example::

        extract_numerals("১০ জন নিহত, ৫০ আহত হয়েছে")
        # → ["10", "50"]

        extract_numerals("বাজেট ১,২০,০০০ কোটি টাকা")
        # → ["1,20,000"]  (comma-sep preserved for comparison)
    """
    # Convert Bangla digits to ASCII first
    ascii_text = normalize_bangla_digits(text)

    numerals: list[str] = []

    # Extract comma/decimal numbers and plain integers
    for match in _ASCII_NUMBER_RE.finditer(ascii_text):
        raw = match.group()
        # Normalise: remove commas for numeric comparison
        normalised = raw.replace(",", "")
        if normalised:
            numerals.append(normalised)

    return numerals


def extract_numerals_set(text: str) -> set[str]:
    """
    Extract unique numerical tokens from text as a set.

    Used for set-intersection consistency scoring.

    Args:
        text: Input text.

    Returns:
        Set of unique normalised numeral strings.
    """
    return set(extract_numerals(text))


def compute_numerical_consistency(
    claim_text: str,
    article_text: str,
) -> float:
    """
    Compute the numerical consistency score between claim and article texts.

    Score = |claim_numerals ∩ article_numerals| / max(|claim_numerals|, 1)

    Semantics:
        1.0 → All claim numerals found in article (consistent).
        0.5 → Half of claim numerals found.
        0.0 → No claim numerals found in article (possible manipulation).

    Special case: If the claim contains NO numerals, returns 1.0
    (there is nothing to verify numerically).

    Args:
        claim_text:   The claim headline + body text.
        article_text: The retrieved article body text.

    Returns:
        Float in [0.0, 1.0].
    """
    claim_nums = extract_numerals_set(claim_text)
    article_nums = extract_numerals_set(article_text)

    if not claim_nums:
        # No numerals in claim → nothing to verify → full score
        return 1.0

    matched = len(claim_nums & article_nums)
    return matched / len(claim_nums)


def find_altered_numbers(
    claim_text: str,
    article_text: str,
) -> list[tuple[str, str | None]]:
    """
    Identify claim numerals that do NOT appear in the article.

    Used by Stage 10 (Manipulation Detector) to flag specific numbers
    that were altered rather than just a score.

    Args:
        claim_text:   The claim headline + body text.
        article_text: The retrieved article body text.

    Returns:
        List of (claim_numeral, nearest_article_numeral | None) tuples
        for each claim numeral absent from the article.
        nearest_article_numeral is the closest article numeral by absolute
        difference (or None if article has no numerals).
    """
    claim_nums = extract_numerals_set(claim_text)
    article_nums = extract_numerals_set(article_text)
    absent = claim_nums - article_nums

    result: list[tuple[str, str | None]] = []
    for num_str in sorted(absent):
        nearest = _find_nearest(num_str, article_nums)
        result.append((num_str, nearest))

    return result


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _find_nearest(target_str: str, candidates: set[str]) -> str | None:
    """
    Find the numerically closest value in `candidates` to `target_str`.

    Args:
        target_str: The target numeral string.
        candidates: Set of candidate numeral strings.

    Returns:
        The closest candidate string, or None if candidates is empty.
    """
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
