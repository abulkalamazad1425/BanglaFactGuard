"""
app/utils/keyword_extractor.py
================================
Keyword and keyphrase extraction utilities for Stage 3 (Query Generator)
and Stage 8 (Similarity Analyzer).

## Approach

Two complementary extraction strategies are combined:

1. **YAKE (Yet Another Keyword Extractor)**: Statistical, language-agnostic,
   works well for Bangla without requiring a trained model. Extracts n-gram
   keyphrases weighted by position, frequency, and co-occurrence.

2. **Simple frequency-based extraction**: A fast fallback using token frequency
   after stopword removal. Used when YAKE fails or for very short texts.

## Why not TF-IDF?

TF-IDF requires a corpus to compute the IDF component. For single-document
keyword extraction (as needed here), YAKE outperforms TF-IDF because it
uses intra-document statistical signals rather than corpus-level IDF.

## Bangla stopwords

A curated set of common Bangla function words is included to filter noise.
These are the most frequent tokens that carry no discriminative information
for search or similarity purposes.

All functions are pure (no I/O, no ML calls).
"""

from __future__ import annotations

import re
from functools import lru_cache

import yake

# ---------------------------------------------------------------------------
# Bangla stopwords
# ---------------------------------------------------------------------------

BANGLA_STOPWORDS: frozenset[str] = frozenset(
    {
        # Common Bangla particles and auxiliaries
        "এই", "এ", "ও", "এবং", "কিন্তু", "তবে", "যে", "যা", "তা", "তার",
        "আর", "না", "নি", "হয়", "হয়েছে", "হয়েছিল", "হবে", "করা", "করে",
        "করেছে", "করেছিল", "করবে", "থেকে", "জন্য", "দিয়ে", "সঙ্গে", "মধ্যে",
        "উপর", "নিচে", "পরে", "আগে", "বলে", "বলা", "বলেছে", "বলেছেন",
        "আছে", "ছিল", "আছেন", "ছিলেন", "একটি", "একটা", "এটি", "এটা",
        "সেটি", "সেটা", "তাদের", "তাকে", "তিনি", "তারা", "আমরা", "আমি",
        "তুমি", "আপনি", "আপনার", "তাই", "সেই", "যেন", "যদি", "কারণ",
        "অথবা", "নয়তো", "ছাড়া", "মতো", "হিসেবে", "ভাবে", "ক্ষেত্রে",
        "সময়", "দিন", "বছর", "মাস", "ঘণ্টা", "বা", "এবার", "তখন",
        "এখন", "যখন", "সব", "সবার", "সবাই", "প্রতি", "প্রতিটি",
        # English stopwords (articles appear in mixed Bangla text)
        "the", "a", "an", "is", "are", "was", "were", "be", "been",
        "being", "have", "has", "had", "do", "does", "did", "will",
        "would", "could", "should", "may", "might", "of", "in", "on",
        "at", "to", "for", "with", "by", "from", "and", "or", "but",
        "not", "this", "that", "it", "he", "she", "they", "we", "you",
    }
)


# ---------------------------------------------------------------------------
# YAKE extractor factory (cached per configuration)
# ---------------------------------------------------------------------------


@lru_cache(maxsize=4)
def _get_yake_extractor(
    language: str,
    max_ngram_size: int,
    dedup_threshold: float,
    num_keywords: int,
) -> yake.KeywordExtractor:
    """
    Return a cached YAKE KeywordExtractor instance.

    YAKE construction is cheap but caching avoids repeated initialisation
    across hundreds of pipeline calls.
    """
    return yake.KeywordExtractor(
        lan=language,
        n=max_ngram_size,
        dedupLim=dedup_threshold,
        dedupFunc="seqm",
        windowsSize=1,
        top=num_keywords,
        features=None,
    )


# ---------------------------------------------------------------------------
# Public extraction functions
# ---------------------------------------------------------------------------


def extract_keywords_yake(
    text: str,
    *,
    language: str = "bn",
    max_ngram_size: int = 2,
    dedup_threshold: float = 0.9,
    num_keywords: int = 10,
) -> list[str]:
    """
    Extract keywords/keyphrases from text using YAKE.

    YAKE is language-agnostic and handles Bangla text without requiring
    a language-specific model. Lower YAKE scores indicate higher relevance
    (counter-intuitively) — we sort ascending and return the top terms.

    Args:
        text:             Input text (Bangla or mixed).
        language:         Language hint for YAKE ("bn" or "en").
        max_ngram_size:   Maximum n-gram length for keyphrases (1=unigrams, 2=bigrams).
        dedup_threshold:  Deduplication threshold for near-duplicate keyphrases.
        num_keywords:     Number of keyphrases to return.

    Returns:
        List of keyword strings, ordered by relevance (most relevant first).
        Returns empty list if extraction fails or text is too short.
    """
    if not text or len(text.strip()) < 10:
        return []

    try:
        extractor = _get_yake_extractor(
            language, max_ngram_size, dedup_threshold, num_keywords
        )
        # YAKE returns list of (keyword, score) tuples; lower score = more relevant
        keywords_with_scores = extractor.extract_keywords(text)
        # Return just the keyword strings, already sorted by relevance
        return [kw for kw, _ in keywords_with_scores]
    except Exception:  # noqa: BLE001
        # YAKE can fail on very short or heavily punctuated texts
        return _fallback_frequency_keywords(text, top_n=num_keywords)


def extract_keywords_simple(
    text: str,
    *,
    top_n: int = 10,
    min_word_length: int = 2,
) -> list[str]:
    """
    Extract keywords using simple token frequency after stopword removal.

    Fast fallback method used when YAKE is unavailable or text is too short
    for statistical extraction to be meaningful.

    Args:
        text:             Input text.
        top_n:            Number of keywords to return.
        min_word_length:  Minimum character length for a token to be considered.

    Returns:
        List of keyword strings ordered by frequency (highest first).
    """
    return _fallback_frequency_keywords(text, top_n=top_n, min_len=min_word_length)


def extract_headline_keywords(
    headline: str,
    *,
    top_n: int = 6,
) -> list[str]:
    """
    Extract the most informative keywords from a news headline.

    Uses unigram YAKE (max_ngram_size=1) for headlines because headlines
    are short and bigrams often span across unrelated concept boundaries.

    Args:
        headline: The normalised news headline.
        top_n:    Number of keywords to extract.

    Returns:
        List of keyword strings.
    """
    return extract_keywords_yake(
        headline,
        max_ngram_size=1,
        num_keywords=top_n,
    )


def extract_body_keywords(
    body: str,
    *,
    top_n: int = 8,
) -> list[str]:
    """
    Extract the most informative keyphrases from a news article body.

    Uses bigram YAKE (max_ngram_size=2) for bodies because longer texts
    contain meaningful multi-word expressions ("ডিজিটাল নিরাপত্তা", "জাতীয় সংসদ").

    Args:
        body:  The normalised article body text.
        top_n: Number of keyphrases to extract.

    Returns:
        List of keyphrase strings.
    """
    return extract_keywords_yake(
        body,
        max_ngram_size=2,
        num_keywords=top_n,
    )


def compute_keyword_overlap(
    keywords_a: list[str],
    keywords_b: list[str],
) -> float:
    """
    Compute Jaccard similarity between two keyword sets.

    Used in Stage 8 (Similarity Analyzer) to compute the keyword_overlap score.

    Jaccard(A, B) = |A ∩ B| / |A ∪ B|

    Args:
        keywords_a: Keywords from the claim.
        keywords_b: Keywords from the retrieved article.

    Returns:
        Float in [0.0, 1.0]. Returns 0.0 if both sets are empty.
    """
    set_a = {k.strip().lower() for k in keywords_a if k.strip()}
    set_b = {k.strip().lower() for k in keywords_b if k.strip()}

    if not set_a and not set_b:
        return 0.0
    if not set_a or not set_b:
        return 0.0

    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


_TOKENIZE_RE = re.compile(r"[\s\.,।॥!?\"'()\[\]{}<>:;]+")


def _fallback_frequency_keywords(
    text: str,
    *,
    top_n: int = 10,
    min_len: int = 2,
) -> list[str]:
    """
    Simple frequency-based keyword extraction with stopword filtering.

    Args:
        text:    Input text.
        top_n:   Number of top-frequency tokens to return.
        min_len: Minimum token length.

    Returns:
        List of keyword strings by frequency (descending).
    """
    tokens = _TOKENIZE_RE.split(text.strip())
    freq: dict[str, int] = {}
    for token in tokens:
        t = token.strip().lower()
        if len(t) >= min_len and t not in BANGLA_STOPWORDS:
            freq[t] = freq.get(t, 0) + 1

    sorted_tokens = sorted(freq.items(), key=lambda x: x[1], reverse=True)
    return [token for token, _ in sorted_tokens[:top_n]]
