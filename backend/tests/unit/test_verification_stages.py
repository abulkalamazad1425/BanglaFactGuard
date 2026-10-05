"""S08-S12: separate responsibilities, separate decisions."""

from __future__ import annotations

from datetime import date

import pytest

from app.core.config import get_settings
from app.core.constants import (
    BodyComparisonStatus,
    ClaimScope,
    ContentStatus,
    DateStatus,
    HeadlineCheckStatus,
    PipelineStageID,
    SourceStatus,
)
from app.features.verification.analysis.decisions import (
    CorrespondenceInputs,
    Metric,
    assess_correspondence,
    decide_date,
    decide_source,
    search_adequate,
)
from app.core.constants import MetricState
from app.features.verification.pipeline.factory import build_verification_stages
from tests.unit.pipeline_helpers import ENTAILS, FakeEmbedder, FakeNLI, article, make_context, run_analysis

HEADLINE = "বাংলাদেশ ব্যাংক নীতি সুদহার বাড়াল"
TITLE = "নীতি সুদহার বাড়িয়েছে বাংলাদেশ ব্যাংক"
BODY = "বাংলাদেশ ব্যাংক আজ নীতি সুদহার বাড়িয়েছে। মূল্যস্ফীতি নিয়ন্ত্রণে এই সিদ্ধান্ত।"


def paraphrase_nli() -> FakeNLI:
    return FakeNLI({(TITLE, HEADLINE): ENTAILS})


def m(v: float | None) -> Metric:
    return Metric(MetricState.COMPUTED, v) if v is not None else Metric()


# ── factory / identifiers ────────────────────────────────────────────────

def test_factory_registers_the_new_stage_order():
    from unittest.mock import MagicMock

    stages = build_verification_stages(
        submission_repo=MagicMock(), result_repo=MagicMock(), article_repo=MagicMock(),
        source_repo=MagicMock(), cache_service=MagicMock(), embedding_service=MagicMock(),
        ner_service=MagicMock(), nli_service=MagicMock(), http_client=MagicMock(),
    )
    assert [s.stage_id for s in stages][-6:] == [
        PipelineStageID.S08_SOURCE_CORRESPONDENCE,
        PipelineStageID.S09_HEADLINE_ALTERATION,
        PipelineStageID.S10_BODY_SIMILARITY,
        PipelineStageID.S11_DATE_VERIFICATION,
        PipelineStageID.S12_RESULT_ASSEMBLY,
        PipelineStageID.S13_RESULT_PERSISTENCE,
    ]


# ── source correspondence ────────────────────────────────────────────────

def test_similar_topic_alone_is_not_correspondence():
    t = get_settings().classification
    corr = assess_correspondence(CorrespondenceInputs(m(0.78), m(0.2), m(0.3)), t)
    assert corr.level == "NONE"


def test_near_identical_title_corresponds_on_its_own():
    t = get_settings().classification
    assert assess_correspondence(CorrespondenceInputs(m(0.9), m(None), m(None)), t).level == "STRONG"


def test_altered_headline_still_corresponds_when_its_keywords_are_in_the_title():
    t = get_settings().classification
    assert assess_correspondence(CorrespondenceInputs(m(0.74), m(0.57), m(0.6)), t).level == "STRONG"


def test_source_absent_and_search_failure_are_different_outcomes():
    assert decide_source(has_evidence=False, search_adequate=True, retrieval_failed=False,
                         correspondence=None)[0] == SourceStatus.NOT_FOUND
    assert decide_source(has_evidence=False, search_adequate=False, retrieval_failed=False,
                         correspondence=None)[0] == SourceStatus.INCOMPLETE
    assert decide_source(has_evidence=False, search_adequate=True, retrieval_failed=True,
                         correspondence=None)[0] == SourceStatus.INCOMPLETE
    assert not search_adequate(4, 1, min_calls=2, min_ratio=0.5)


async def test_s08_prefers_a_corresponding_candidate_over_rank_one():
    unrelated = article("চট্টগ্রাম বন্দরে নতুন জাহাজ ভিড়েছে", url="https://prothomalo.com/a/2")
    genuine = article(TITLE, BODY, url="https://prothomalo.com/a/1")
    ctx = make_context(HEADLINE, articles=[unrelated, genuine])
    ctx = await run_analysis(ctx, nli=paraphrase_nli())
    assert ctx.source_status == SourceStatus.CONFIRMED
    assert ctx.top_article.url == genuine.url
    assert ctx.content_status == ContentStatus.MATCHED


# ── headline alteration independence ─────────────────────────────────────

async def test_changing_the_source_body_never_changes_the_headline_verdict():
    verdicts = set()
    for body in (BODY, "সম্পূর্ণ ভিন্ন একটি প্রতিবেদন যেখানে সুদহার কমানোর কথা বলা হয়েছে।", None):
        ctx = await run_analysis(make_context(HEADLINE, top=article(TITLE, body)), nli=paraphrase_nli())
        assert ctx.analysis.headline_alteration.source_title == TITLE
        verdicts.add((ctx.content_status, ctx.headline_check_status))
    assert verdicts == {(ContentStatus.MATCHED, HeadlineCheckStatus.COMPLETED)}


async def test_headline_comparison_never_reads_the_source_body():
    nli = paraphrase_nli()
    ctx = await run_analysis(make_context(HEADLINE, top=article(TITLE, BODY)), nli=nli)
    assert ctx.content_status == ContentStatus.MATCHED
    assert all(BODY not in premise and BODY not in hyp for premise, hyp in nli.calls)


async def test_body_scores_do_not_decide_the_headline_verdict():
    """Identical bodies (scores of 1.0) cannot rescue an altered headline,
    and wholly different bodies cannot alter a matched one."""
    altered = await run_analysis(make_context(
        "বাংলাদেশ ব্যাংক নীতি সুদহার কমাল ৫ শতাংশ", body=BODY,
        top=article("নীতি সুদহার বাড়িয়েছে বাংলাদেশ ব্যাংক ২ শতাংশ", BODY),
    ))
    assert altered.analysis.body_similarity.tfidf_cosine.value == pytest.approx(1.0)
    assert altered.content_status == ContentStatus.ALTERED

    matched = await run_analysis(make_context(
        HEADLINE, body="চট্টগ্রাম বন্দরে নতুন জাহাজ ভিড়েছে।", top=article(TITLE, BODY),
    ), nli=paraphrase_nli())
    assert matched.analysis.body_similarity.jaccard.value < 0.2
    assert matched.content_status == ContentStatus.MATCHED


async def test_photo_card_and_headline_only_claims_get_the_same_headline_rule():
    for scope in (ClaimScope.HEADLINE_ONLY, ClaimScope.HEADLINE_WITH_BODY):
        ctx = await run_analysis(
            make_context(HEADLINE, body=BODY, scope=scope, top=article(TITLE, BODY)), nli=paraphrase_nli()
        )
        assert ctx.content_status == ContentStatus.MATCHED


# ── no source / failed search ────────────────────────────────────────────

async def test_source_not_found_has_no_headline_verdict():
    ctx = await run_analysis(make_context(HEADLINE, body=BODY, search_adequate=True))
    assert ctx.source_status == SourceStatus.NOT_FOUND
    assert ctx.content_status is None
    assert ctx.headline_check_status == HeadlineCheckStatus.SOURCE_NOT_FOUND
    assert ctx.analysis.body_similarity.status == BodyComparisonStatus.UNAVAILABLE


async def test_failed_search_is_not_reported_as_source_not_found():
    ctx = make_context(HEADLINE, search_adequate=False)
    ctx.search_errors, ctx.search_success = 4, 0
    ctx = await run_analysis(ctx)
    assert ctx.source_status == SourceStatus.INCOMPLETE
    assert ctx.headline_check_status == HeadlineCheckStatus.SOURCE_CHECK_INCOMPLETE
    assert "not a finding" in ctx.analysis.headline_alteration.reason


async def test_untitled_source_article_has_no_headline_verdict():
    from app.features.verification.analysis.headline_comparison import HeadlineComparator
    from app.features.verification.pipeline.stages.s09_headline_alteration import HeadlineAlterationStage

    ctx = make_context(HEADLINE, top=article(None, BODY))
    ctx.source_status = SourceStatus.CONFIRMED
    ctx = await HeadlineAlterationStage(HeadlineComparator(FakeNLI(), FakeEmbedder())).execute(ctx)
    assert ctx.content_status is None
    assert ctx.headline_check_status == HeadlineCheckStatus.SOURCE_TITLE_MISSING
    assert ctx.stage_errors[PipelineStageID.S09_HEADLINE_ALTERATION.value]


# ── body similarity stage ────────────────────────────────────────────────

async def test_headline_only_claim_skips_body_similarity():
    ctx = await run_analysis(make_context(HEADLINE, top=article(TITLE, BODY)), nli=paraphrase_nli())
    assert ctx.analysis.body_similarity.status == BodyComparisonStatus.SKIPPED
    assert ctx.analysis.body_similarity.tfidf_cosine is None


async def test_missing_source_body_is_unavailable_with_a_reason():
    ctx = await run_analysis(make_context(HEADLINE, body=BODY, top=article(TITLE, None)), nli=paraphrase_nli())
    body = ctx.analysis.body_similarity
    assert body.status == BodyComparisonStatus.UNAVAILABLE and "body" in body.reason
    assert body.semantic_cosine is None


async def test_failed_semantic_metric_keeps_the_other_scores():
    ctx = make_context(HEADLINE, body=BODY, top=article(TITLE, BODY))
    ctx = await run_analysis(ctx, embedder=FakeEmbedder(fail=True), nli=paraphrase_nli())
    body = ctx.analysis.body_similarity
    assert body.status == BodyComparisonStatus.COMPUTED
    assert body.semantic_cosine.available is False and body.semantic_cosine.value is None
    assert body.jaccard.available and body.tfidf_cosine.available and body.normalized_levenshtein.available


# ── date and assembly ────────────────────────────────────────────────────

def test_date_rules():
    assert decide_date(None, date(2026, 6, 7), source_confirmed=True) is None
    assert decide_date(date(2026, 6, 7), None, source_confirmed=True) == DateStatus.INCOMPLETE
    assert decide_date(date(2026, 6, 7), date(2026, 6, 8), source_confirmed=True) == DateStatus.MISMATCHED
    assert decide_date(date(2026, 6, 7), date(2026, 6, 7), source_confirmed=False) is None


async def test_wrong_claimed_date_is_mismatched_while_headline_matches():
    ctx = await run_analysis(make_context(HEADLINE, published_date=date(2026, 1, 1), top=article(TITLE, BODY)),
                             nli=paraphrase_nli())
    assert ctx.content_status == ContentStatus.MATCHED
    assert ctx.date_status == DateStatus.MISMATCHED
    assert ctx.analysis.date.claimed_date == date(2026, 1, 1)


async def test_assembly_explains_dimensions_separately_without_an_overall_verdict():
    ctx = await run_analysis(make_context(HEADLINE, body=BODY, top=article(TITLE, BODY)), nli=paraphrase_nli())
    assert "Headline Alteration: matched" in ctx.reasoning
    assert "not part of any verdict" in ctx.reasoning
    assert not any(w in ctx.reasoning.lower() for w in ("fake", "misleading"))
    assert 0.0 < ctx.confidence <= 1.0
    assert ctx.analysis.pipeline_version and ctx.analysis.claim_scope == ClaimScope.HEADLINE_WITH_BODY
