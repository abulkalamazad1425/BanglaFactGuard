"""S10: body scores are measurements only, and only for a claim with a body."""

import pytest

from app.core.constants import BodyComparisonStatus, ClaimScope, SourceStatus
from app.features.verification.pipeline.stages.s10_body_similarity import BodySimilarityStage
from tests.helpers.pipeline import FakeEmbedder, article, make_context

HEADLINE = "বাংলাদেশ ব্যাংক নীতি সুদহার বাড়াল"
BODY = "বাংলাদেশ ব্যাংক আজ নীতি সুদহার বাড়িয়েছে। মূল্যস্ফীতি নিয়ন্ত্রণে এই সিদ্ধান্ত।"


def ctx(*, body=BODY, source_body=BODY, status=SourceStatus.CONFIRMED, scope=None):
    c = make_context(HEADLINE, body=body, scope=scope, top=article(HEADLINE, source_body))
    c.source_status = status
    return c


async def measure(c, embedder=None):
    return (await BodySimilarityStage(embedder or FakeEmbedder()).execute(c))


async def test_all_four_scores_are_measured_without_touching_the_headline_verdict():
    out = await measure(ctx())
    report = out.analysis.body_similarity
    assert report.status == BodyComparisonStatus.COMPUTED and out.content_status is None
    assert all(getattr(report, m).value == pytest.approx(1.0, abs=1e-4)
               for m in ("tfidf_cosine", "jaccard", "normalized_levenshtein", "semantic_cosine"))


async def test_a_failed_metric_is_recorded_and_the_others_kept():
    out = await measure(ctx(), FakeEmbedder(fail=True))
    report = out.analysis.body_similarity
    assert report.status == BodyComparisonStatus.COMPUTED and not report.semantic_cosine.available
    assert report.jaccard.available and "semantic_cosine" in next(iter(out.stage_errors.values()))


@pytest.mark.parametrize("kwargs,status,reason", [
    (dict(body=None), BodyComparisonStatus.SKIPPED, "no body"),
    (dict(scope=ClaimScope.HEADLINE_ONLY), BodyComparisonStatus.SKIPPED, "no body"),
    (dict(status=SourceStatus.NOT_FOUND), BodyComparisonStatus.UNAVAILABLE, "No corresponding source article"),
    (dict(status=SourceStatus.INCOMPLETE), BodyComparisonStatus.UNAVAILABLE, "could not be completed"),
    (dict(source_body=None), BodyComparisonStatus.UNAVAILABLE, "could not be extracted"),
])
async def test_nothing_is_scored_without_both_bodies(kwargs, status, reason):
    report = (await measure(ctx(**kwargs))).analysis.body_similarity
    assert report.status == status and reason in report.reason and report.tfidf_cosine is None
