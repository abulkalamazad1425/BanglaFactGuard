"""Claim body vs source body: four measurements, never a verdict."""

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
from tests.unit.pipeline_helpers import FakeEmbedder

BODY = "ঢাকায় আজ ভারী বৃষ্টিতে বিভিন্ন সড়কে জলাবদ্ধতা দেখা দিয়েছে। নগরবাসী চরম দুর্ভোগে পড়েছেন।"
OTHER = "চট্টগ্রাম বন্দরে নতুন জাহাজ ভিড়েছে এবং পণ্য খালাস শুরু হয়েছে।"


async def test_identical_bodies_score_one_on_every_metric():
    r = await compare_bodies(BODY, BODY, FakeEmbedder())
    assert r.status == BodyComparisonStatus.COMPUTED
    for name in bs.METRIC_NAMES:
        assert r.metrics[name].available
        assert r.metrics[name].value == pytest.approx(1.0, abs=1e-4)


async def test_unrelated_bodies_score_low_but_are_real_measurements():
    r = await compare_bodies(BODY, OTHER, FakeEmbedder())
    assert r.status == BodyComparisonStatus.COMPUTED
    assert r.metrics["jaccard"].value < 0.2
    assert r.metrics["tfidf_cosine"].value < 0.2


def test_jaccard_is_unique_word_intersection_over_union():
    m = jaccard_similarity("ক খ গ গ", "খ গ ঘ")
    assert m.available and m.value == pytest.approx(2 / 4)


def test_levenshtein_follows_the_documented_formula():
    m = normalized_levenshtein_similarity("আমার সোনার বাংলা", "আমার সোনার বাংলাদেশ")
    a, b = "আমার সোনার বাংলা", "আমার সোনার বাংলাদেশ"
    assert m.value == pytest.approx(round(1 - m.details["edit_distance"] / max(len(a), len(b)), 4))
    assert m.details["truncated"] is False


def test_levenshtein_records_truncation_for_long_text(monkeypatch):
    monkeypatch.setattr(bs, "LEVENSHTEIN_MAX_CHARS", 50)
    m = normalized_levenshtein_similarity(BODY * 5, BODY * 6)
    assert m.available and m.details["truncated"] is True
    assert m.details["claim_chars_compared"] == 50 and m.details["claim_chars_total"] > 50


def test_tfidf_keeps_numbers_and_negation():
    same = tfidf_cosine_similarity("৫ জন নিহত হননি", "৫ জন নিহত হননি")
    changed = tfidf_cosine_similarity("৫ জন নিহত হননি", "১০ জন নিহত হয়েছেন")
    assert same.value == pytest.approx(1.0) and changed.value < same.value


async def test_semantic_raw_cosine_is_kept_and_display_is_clipped_to_zero():
    class Opposite(FakeEmbedder):
        async def encode_batch(self, texts):
            return [np.array([1.0, 0.0]) if i == 0 else np.array([-1.0, 0.0]) for i, _ in enumerate(texts)]

    m = await semantic_cosine_similarity("এক বাক্য।", "অন্য বাক্য।", Opposite())
    assert m.available and m.raw_value == pytest.approx(-1.0) and m.value == 0.0
    assert "max(0, raw)" in m.details["display_transform"]


async def test_long_bodies_are_chunked_and_coverage_is_recorded():
    long_body = " ".join([BODY] * 40)
    m = await semantic_cosine_similarity(long_body, long_body, FakeEmbedder())
    assert m.details["claim_chunks"] > 1 and m.details["claim_truncated"] is False
    assert m.value == pytest.approx(1.0, abs=1e-4)


async def test_missing_claim_body_skips_comparison():
    r = await compare_bodies(None, BODY, FakeEmbedder())
    assert r.status == BodyComparisonStatus.SKIPPED and r.metrics == {}


async def test_missing_source_body_is_unavailable_never_zero():
    r = await compare_bodies(BODY, "  ", FakeEmbedder())
    assert r.status == BodyComparisonStatus.UNAVAILABLE
    assert r.metrics == {} and "could not be extracted" in r.reason


async def test_one_failing_metric_keeps_the_others():
    r = await compare_bodies(BODY, BODY, FakeEmbedder(fail=True))
    assert r.status == BodyComparisonStatus.COMPUTED
    sem = r.metrics["semantic_cosine"]
    assert not sem.available and sem.value is None and "embedding model failed" in sem.reason
    assert all(r.metrics[n].available for n in ("tfidf_cosine", "jaccard", "normalized_levenshtein"))


async def test_metric_exception_is_isolated(monkeypatch):
    def boom(a, b):
        raise ValueError("bad input")

    monkeypatch.setattr(bs, "jaccard_similarity", boom)
    r = await bs.compare_bodies(BODY, BODY, FakeEmbedder())
    assert not r.metrics["jaccard"].available and r.metrics["jaccard"].value is None
    assert r.metrics["tfidf_cosine"].available


async def test_bodies_without_words_are_empty_input_never_a_zero_score():
    skipped = await compare_bodies("।।।", BODY, FakeEmbedder())
    assert skipped.status == BodyComparisonStatus.SKIPPED and skipped.metrics == {}
    unavailable = await compare_bodies(BODY, "?!", FakeEmbedder())
    assert unavailable.status == BodyComparisonStatus.UNAVAILABLE and unavailable.metrics == {}
