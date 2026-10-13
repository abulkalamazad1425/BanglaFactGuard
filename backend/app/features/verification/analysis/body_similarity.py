from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field

import Levenshtein
import numpy as np
import structlog

from app.core.constants import BodyComparisonStatus
from app.features.verification.analysis.text import chunk_text, content_tokens, tokenize

logger = structlog.get_logger(__name__)

LEVENSHTEIN_MAX_CHARS = 20_000
SEMANTIC_CHUNK_CHARS = 450
SEMANTIC_MAX_CLAIM_CHUNKS = 120
SEMANTIC_MAX_SOURCE_CHUNKS = 200
SEMANTIC_MODEL = "sentence-transformers/LaBSE"

METRIC_NAMES = ("tfidf_cosine", "jaccard", "normalized_levenshtein", "semantic_cosine")


@dataclass
class MetricResult:
    available: bool
    value: float | None = None
    raw_value: float | None = None
    reason: str | None = None
    details: dict = field(default_factory=dict)


@dataclass
class BodySimilarityResult:
    status: BodyComparisonStatus
    reason: str | None = None
    metrics: dict[str, MetricResult] = field(default_factory=dict)
    claim_chars: int | None = None
    source_chars: int | None = None


def _light_normalise(text: str) -> str:
    t = unicodedata.normalize("NFC", text or "")
    t = re.sub("[​⁠﻿]", "", t)
    return re.sub(r"\s+", " ", t).strip()


def tfidf_cosine_similarity(a: str, b: str) -> MetricResult:
    ta, tb = content_tokens(a), content_tokens(b)
    if not ta or not tb:
        return MetricResult(False, reason="a body has no content words to compare")
    ca, cb = Counter(ta), Counter(tb)

    def idf(term: str) -> float:
        df = (term in ca) + (term in cb)
        return math.log((1 + 2) / (1 + df)) + 1.0

    va = {t: (n / len(ta)) * idf(t) for t, n in ca.items()}
    vb = {t: (n / len(tb)) * idf(t) for t, n in cb.items()}
    na = math.sqrt(sum(v * v for v in va.values()))
    nb = math.sqrt(sum(v * v for v in vb.values()))
    if na == 0.0 or nb == 0.0:
        return MetricResult(False, reason="empty TF-IDF vector")
    cos = sum(w * vb.get(t, 0.0) for t, w in va.items()) / (na * nb)
    cos = max(0.0, min(1.0, cos))
    return MetricResult(True, round(cos, 4), raw_value=round(cos, 6),
                        details={"claim_terms": len(ca), "source_terms": len(cb), "shared_terms": len(ca.keys() & cb.keys())})


def jaccard_similarity(a: str, b: str) -> MetricResult:
    sa, sb = set(tokenize(a)), set(tokenize(b))
    if not sa or not sb:
        return MetricResult(False, reason="a body has no words to compare")
    inter, union = len(sa & sb), len(sa | sb)
    value = inter / union
    return MetricResult(True, round(value, 4), raw_value=round(value, 6),
                        details={"shared_unique_words": inter, "all_unique_words": union})


def normalized_levenshtein_similarity(a: str, b: str) -> MetricResult:
    na, nb = _light_normalise(a), _light_normalise(b)
    if not na or not nb:
        return MetricResult(False, reason="a body is empty after normalisation")
    truncated = len(na) > LEVENSHTEIN_MAX_CHARS or len(nb) > LEVENSHTEIN_MAX_CHARS
    ca, cb = na[:LEVENSHTEIN_MAX_CHARS], nb[:LEVENSHTEIN_MAX_CHARS]
    distance = Levenshtein.distance(ca, cb)
    value = max(0.0, min(1.0, 1 - distance / max(len(ca), len(cb))))
    return MetricResult(
        True, round(value, 4), raw_value=round(value, 6),
        details={
            "edit_distance": distance,
            "claim_chars_compared": len(ca), "source_chars_compared": len(cb),
            "claim_chars_total": len(na), "source_chars_total": len(nb),
            "truncated": truncated,
        },
    )


async def semantic_cosine_similarity(a: str, b: str, embedder) -> MetricResult:
    if embedder is None:
        return MetricResult(False, reason="embedding model is not configured")
    claim_chunks, claim_trunc = chunk_text(a, max_chars=SEMANTIC_CHUNK_CHARS, max_chunks=SEMANTIC_MAX_CLAIM_CHUNKS)
    src_chunks, src_trunc = chunk_text(b, max_chars=SEMANTIC_CHUNK_CHARS, max_chunks=SEMANTIC_MAX_SOURCE_CHUNKS)
    if not claim_chunks or not src_chunks:
        return MetricResult(False, reason="no comparable text after chunking")
    try:
        vectors = await embedder.encode_batch(claim_chunks + src_chunks)
        ce = np.vstack(vectors[: len(claim_chunks)])
        se = np.vstack(vectors[len(claim_chunks):])
        best = (ce @ se.T).max(axis=1)
        if not np.isfinite(best).all():
            raise ValueError("non-finite embedding similarity")
    except Exception as exc:  # noqa: BLE001
        logger.warning("body_semantic_similarity_failed", error=str(exc))
        return MetricResult(False, reason=f"embedding model failed: {str(exc)[:160]}")
    weights = np.array([len(c) for c in claim_chunks], dtype=float)
    raw = float((best * weights).sum() / weights.sum())
    return MetricResult(
        True, round(max(0.0, min(1.0, raw)), 4), raw_value=round(raw, 6),
        details={
            "model": SEMANTIC_MODEL,
            "aggregation": "claim-chunk-length-weighted mean of each claim chunk's best source-chunk cosine",
            "raw_range": "[-1, 1]",
            "display_transform": "max(0, raw) — negative similarity shown as 0",
            "claim_chunks": len(claim_chunks), "source_chunks": len(src_chunks),
            "chunk_chars": SEMANTIC_CHUNK_CHARS,
            "claim_truncated": claim_trunc, "source_truncated": src_trunc,
        },
    )


async def compare_bodies(claim_body: str | None, source_body: str | None, embedder) -> BodySimilarityResult:
    claim = (claim_body or "").strip()
    source = (source_body or "").strip()
    if not tokenize(claim):
        return BodySimilarityResult(BodyComparisonStatus.SKIPPED, "The claim has no body, so body similarity was not computed.")
    if not tokenize(source):
        return BodySimilarityResult(
            BodyComparisonStatus.UNAVAILABLE,
            "The source article's body could not be extracted, so the claim body could not be compared.",
            claim_chars=len(claim),
        )

    metrics: dict[str, MetricResult] = {}
    for name, fn in (("tfidf_cosine", tfidf_cosine_similarity), ("jaccard", jaccard_similarity),
                     ("normalized_levenshtein", normalized_levenshtein_similarity)):
        try:
            metrics[name] = fn(claim, source)
        except Exception as exc:  # noqa: BLE001
            logger.warning("body_metric_failed", metric=name, error=str(exc))
            metrics[name] = MetricResult(False, reason=f"computation failed: {str(exc)[:160]}")
    try:
        metrics["semantic_cosine"] = await semantic_cosine_similarity(claim, source, embedder)
    except Exception as exc:  # noqa: BLE001
        metrics["semantic_cosine"] = MetricResult(False, reason=f"computation failed: {str(exc)[:160]}")

    if not any(m.available for m in metrics.values()):
        return BodySimilarityResult(
            BodyComparisonStatus.UNAVAILABLE, "None of the body similarity metrics could be computed.",
            metrics=metrics, claim_chars=len(claim), source_chars=len(source),
        )
    return BodySimilarityResult(BodyComparisonStatus.COMPUTED, None, metrics, len(claim), len(source))
