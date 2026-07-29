
from __future__ import annotations

import re
from functools import lru_cache

import yake





BANGLA_STOPWORDS: frozenset[str] = frozenset(
    {

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

        "the", "a", "an", "is", "are", "was", "were", "be", "been",
        "being", "have", "has", "had", "do", "does", "did", "will",
        "would", "could", "should", "may", "might", "of", "in", "on",
        "at", "to", "for", "with", "by", "from", "and", "or", "but",
        "not", "this", "that", "it", "he", "she", "they", "we", "you",
    }
)







@lru_cache(maxsize=4)
def _get_yake_extractor(
    language: str,
    max_ngram_size: int,
    dedup_threshold: float,
    num_keywords: int,
) -> yake.KeywordExtractor:
    return yake.KeywordExtractor(
        lan=language,
        n=max_ngram_size,
        dedupLim=dedup_threshold,
        dedupFunc="seqm",
        windowsSize=1,
        top=num_keywords,
        features=None,
    )







def extract_keywords_yake(
    text: str,
    *,
    language: str = "bn",
    max_ngram_size: int = 2,
    dedup_threshold: float = 0.9,
    num_keywords: int = 10,
) -> list[str]:
    if not text or len(text.strip()) < 10:
        return []

    try:
        extractor = _get_yake_extractor(
            language, max_ngram_size, dedup_threshold, num_keywords
        )

        keywords_with_scores = extractor.extract_keywords(text)

        return [kw for kw, _ in keywords_with_scores]
    except Exception:

        return _fallback_frequency_keywords(text, top_n=num_keywords)


def extract_keywords_with_scores(
    text: str,
    *,
    language: str = "bn",
    max_ngram_size: int = 2,
    dedup_threshold: float = 0.9,
    num_keywords: int = 10,
) -> list[tuple[str, float]]:
    if not text or len(text.strip()) < 10:
        return []

    try:
        extractor = _get_yake_extractor(
            language, max_ngram_size, dedup_threshold, num_keywords
        )
        raw = extractor.extract_keywords(text)

        weighted = [(kw, 1.0 / (1.0 + score)) for kw, score in raw]

        weighted.sort(key=lambda x: x[1], reverse=True)
        return weighted
    except Exception:

        fallback_kws = _fallback_frequency_keywords(text, top_n=num_keywords)
        return [(kw, 1.0) for kw in fallback_kws]


def extract_keywords_simple(
    text: str,
    *,
    top_n: int = 10,
    min_word_length: int = 2,
) -> list[str]:
    return _fallback_frequency_keywords(text, top_n=top_n, min_len=min_word_length)


def extract_headline_keywords(
    headline: str,
    *,
    top_n: int = 6,
) -> list[str]:
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
    return extract_keywords_yake(
        body,
        max_ngram_size=2,
        num_keywords=top_n,
    )


def compute_keyword_overlap(
    keywords_a: list[str],
    keywords_b: list[str],
) -> float:
    set_a = {k.strip().lower() for k in keywords_a if k.strip()}
    set_b = {k.strip().lower() for k in keywords_b if k.strip()}

    if not set_a and not set_b:
        return 0.0
    if not set_a or not set_b:
        return 0.0

    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union


def compute_weighted_keyword_overlap(
    keywords_a: list[tuple[str, float]],
    keywords_b: list[tuple[str, float]],
) -> float:
    if not keywords_a and not keywords_b:
        return 0.0


    weights_a: dict[str, float] = {}
    for kw, w in keywords_a:
        key = kw.strip().lower()
        if key:
            weights_a[key] = max(weights_a.get(key, 0.0), w)

    weights_b: dict[str, float] = {}
    for kw, w in keywords_b:
        key = kw.strip().lower()
        if key:
            weights_b[key] = max(weights_b.get(key, 0.0), w)

    if not weights_a or not weights_b:
        return 0.0

    all_keywords = set(weights_a.keys()) | set(weights_b.keys())
    matched_weight = 0.0
    total_weight = 0.0

    for kw in all_keywords:
        w = max(weights_a.get(kw, 0.0), weights_b.get(kw, 0.0))
        total_weight += w
        if kw in weights_a and kw in weights_b:
            matched_weight += w

    if total_weight == 0.0:
        return 0.0

    return matched_weight / total_weight







_TOKENIZE_RE = re.compile(r"[\s\.,।॥!?\"'()\[\]{}<>:;]+")


def _fallback_frequency_keywords(
    text: str,
    *,
    top_n: int = 10,
    min_len: int = 2,
) -> list[str]:
    tokens = _TOKENIZE_RE.split(text.strip())
    freq: dict[str, int] = {}
    for token in tokens:
        t = token.strip().lower()
        if len(t) >= min_len and t not in BANGLA_STOPWORDS:
            freq[t] = freq.get(t, 0) + 1

    sorted_tokens = sorted(freq.items(), key=lambda x: x[1], reverse=True)
    return [token for token, _ in sorted_tokens[:top_n]]
