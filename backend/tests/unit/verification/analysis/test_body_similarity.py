"""Claim body vs source body: four independent measurements, never a verdict."""

from __future__ import annotations

import numpy as np
import pytest

from app.core.constants import BodyComparisonStatus
from app.features.verification.analysis import body_similarity as bs
from app.features.verification.analysis.body_similarity import (
    compare_bodies,
    jaccard_similarity,
    normalized_levenshtein_similarity,
    semantic_cosine_similarity,
    tfidf_cosine_similarity,
)
from tests.helpers.pipeline import FakeEmbedder

BODY = "ঢাকায় আজ ভারী বৃষ্টিতে বিভিন্ন সড়কে জলাবদ্ধতা দেখা দিয়েছে। নগরবাসী চরম দুর্ভোগে পড়েছেন।"
OTHER = "চট্টগ্রাম বন্দরে নতুন জাহাজ ভিড়েছে এবং পণ্য খালাস শুরু হয়েছে।"


async def test_identical_bodies_score_one_and_unrelated_bodies_score_low():
    same = await compare_bodies(BODY, BODY, FakeEmbedder())
    assert same.status == BodyComparisonStatus.COMPUTED
    assert all(same.metrics[n].value == pytest.approx(1.0, abs=1e-4) for n in bs.METRIC_NAMES)
    different = await compare_bodies(BODY, OTHER, FakeEmbedder())
    assert different.status == BodyComparisonStatus.COMPUTED  # a low score is still a measurement
    assert different.metrics["jaccard"].value < 0.2 and different.metrics["tfidf_cosine"].value < 0.2


def test_lexical_metrics_follow_their_documented_formulas(monkeypatch):
    assert jaccard_similarity("ক খ গ গ", "খ গ ঘ").value == pytest.approx(2 / 4)
    a, b = "আমার সোনার বাংলা", "আমার সোনার বাংলাদেশ"
    lev = normalized_levenshtein_similarity(a, b)
    assert lev.value == pytest.approx(round(1 - lev.details["edit_distance"] / max(len(a), len(b)), 4))
    assert lev.details["truncated"] is False
    monkeypatch.setattr(bs, "LEVENSHTEIN_MAX_CHARS", 50)
    long = normalized_levenshtein_similarity(BODY * 5, BODY * 6)
    assert long.details["truncated"] and long.details["claim_chars_compared"] == 50
    # numbers and negation are kept as TF-IDF terms
    same = tfidf_cosine_similarity("৫ জন নিহত হননি", "৫ জন নিহত হননি")
    changed = tfidf_cosine_similarity("৫ জন নিহত হননি", "১০ জন নিহত হয়েছেন")
    assert same.value == pytest.approx(1.0) and changed.value < same.value


async def test_semantic_similarity_keeps_the_raw_cosine_and_chunks_long_text():
    class Opposite(FakeEmbedder):
        async def encode_batch(self, texts):
            return [np.array([1.0, 0.0]) if i == 0 else np.array([-1.0, 0.0]) for i, _ in enumerate(texts)]

    m = await semantic_cosine_similarity("এক বাক্য।", "অন্য বাক্য।", Opposite())
    assert m.raw_value == pytest.approx(-1.0) and m.value == 0.0
    long = " ".join([BODY] * 40)
    m = await semantic_cosine_similarity(long, long, FakeEmbedder())
    assert m.details["claim_chunks"] > 1 and m.details["claim_truncated"] is False
    assert m.value == pytest.approx(1.0, abs=1e-4)
    assert not (await semantic_cosine_similarity(BODY, BODY, None)).available


@pytest.mark.parametrize("claim,source,status", [
    (None, BODY, BodyComparisonStatus.SKIPPED),
    ("।।।", BODY, BodyComparisonStatus.SKIPPED),        # no words: empty input, never a zero score
    (BODY, "  ", BodyComparisonStatus.UNAVAILABLE),
    (BODY, "?!", BodyComparisonStatus.UNAVAILABLE),
])
async def test_missing_bodies_are_never_scored(claim, source, status):
    r = await compare_bodies(claim, source, FakeEmbedder())
    assert r.status == status and r.metrics == {} and r.reason


async def test_a_failing_metric_never_discards_the_others(monkeypatch):
    def boom(a, b):
        raise ValueError("bad input")

    monkeypatch.setattr(bs, "jaccard_similarity", boom)
    r = await compare_bodies(BODY, BODY, FakeEmbedder(fail=True))
    assert r.status == BodyComparisonStatus.COMPUTED
    assert not r.metrics["jaccard"].available and r.metrics["jaccard"].value is None
    assert "embedding model failed" in r.metrics["semantic_cosine"].reason
    assert r.metrics["tfidf_cosine"].available and r.metrics["normalized_levenshtein"].available

    for name in ("tfidf_cosine_similarity", "normalized_levenshtein_similarity"):
        monkeypatch.setattr(bs, name, boom)
    none_left = await compare_bodies(BODY, BODY, FakeEmbedder(fail=True))
    assert none_left.status == BodyComparisonStatus.UNAVAILABLE
