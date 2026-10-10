"""S08: did the outlet publish THIS report? A matching result that could not
be read is INCOMPLETE - never NOT_FOUND, never replaced by a weaker stand-in."""

from __future__ import annotations

import pytest

from app.core.constants import MetricState, SearchProvider, SourceStatus
from app.features.articles.schemas import CandidateArticleSchema
from app.features.verification import source_policy
from app.features.verification.pipeline.stages.s08_source_correspondence import (
    SourceCorrespondenceStage,
)
from tests.helpers.pipeline import FakeEmbedder, article, make_context

CLAIM = "জঙ্গল সলিমপুরে সারদার আদলে পুলিশ একাডেমি হচ্ছে"
REWORDED = "সলিমপুরে সারদার আদলে পুলিশ একাডেমি, কারাগারও হবে"
LOOSE = "জঙ্গল সলিমপুরে পুলিশ একাডেমি ও কারাগার তৈরি করা হবে"
BODY = "জঙ্গল সলিমপুরে সারদার আদলে পুলিশ একাডেমি হচ্ছে বলে জানিয়েছেন স্বরাষ্ট্রমন্ত্রী।"
UNRELATED = "চট্টগ্রাম বন্দরে নতুন জাহাজ ভিড়েছে"
BLOCKED = "https://www.kalerkantho.com/online/dhaka/2026/10/09/1750312"


def blocked(ctx, title: str):
    ctx.candidate_urls = [CandidateArticleSchema(url=BLOCKED, title_snippet=f"{title} - কালের কণ্ঠ",
                                                 search_provider=SearchProvider.PY_GOOGLE_NEWS, query_type="headline")]
    ctx.failed_extraction_urls = [BLOCKED + "/amp"]
    return ctx


async def correspond(ctx, embedder=None):
    return await SourceCorrespondenceStage(embedder or FakeEmbedder()).execute(ctx)


async def test_the_best_corresponding_article_is_selected_not_rank_one():
    unrelated = article(UNRELATED, url="https://prothomalo.com/a/2")
    reworded = article(REWORDED, BODY, url="https://www.prothomalo.com/video/x1")
    exact = article(CLAIM, BODY, url="https://dailynayadiganta.com/post/1059596")
    ctx = await correspond(make_context(CLAIM, articles=[unrelated, reworded, exact]))
    assert ctx.source_status == SourceStatus.CONFIRMED and ctx.top_article.url == exact.url
    assert ctx.analysis.metrics["headline_title_similarity"].value == pytest.approx(1.0)
    assert ctx.analysis.search.attempted == 4  # search accounting is recorded


async def test_a_claim_quoting_the_kicker_selects_that_headline_line():
    kicker = "প্রধানমন্ত্রীর সঙ্গে আবরার ফাহাদের পরিবারের সাক্ষাৎ"
    page = article("রায় দ্রুত কার্যকরের দাবি", url="https://www.mzamin.com/article/47841")
    page = page.model_copy(update={"title_variants": [kicker]})
    ctx = await correspond(make_context(kicker, articles=[page]))
    assert ctx.source_status == SourceStatus.CONFIRMED and ctx.top_article.title == kicker


@pytest.mark.parametrize("articles,search_title,status", [
    ([], CLAIM, SourceStatus.INCOMPLETE),                                    # matching result blocked, nothing read
    ([article(LOOSE, BODY, url="https://dailyinqilab.com/n/947665")], CLAIM, SourceStatus.INCOMPLETE),  # no weaker stand-in
    ([article(CLAIM, BODY, url="https://dailynayadiganta.com/p/1")], CLAIM, SourceStatus.CONFIRMED),   # exact report was read
    ([article(UNRELATED, url="https://prothomalo.com/a/9")], "ক্রিকেট দলের অধিনায়ক ঘোষণা", SourceStatus.NOT_FOUND),
])
async def test_a_blocked_search_result_only_matters_when_it_matches_better(articles, search_title, status):
    ctx = await correspond(blocked(make_context(CLAIM, articles=articles), search_title))
    assert ctx.source_status == status
    if status == SourceStatus.INCOMPLETE:
        assert "blocked automated access" in ctx.analysis.source_basis[-1]


@pytest.mark.parametrize("adequate,status", [(True, SourceStatus.NOT_FOUND), (False, SourceStatus.INCOMPLETE)])
async def test_without_evidence_only_an_adequate_search_means_not_found(adequate, status):
    assert (await correspond(make_context(CLAIM, search_adequate=adequate))).source_status == status


async def test_a_failed_similarity_model_is_recorded_and_keywords_still_decide():
    ctx = await correspond(make_context(CLAIM, articles=[article(CLAIM, BODY)]), FakeEmbedder(fail=True))
    assert ctx.analysis.metrics["headline_title_similarity"].state == MetricState.UNAVAILABLE
    assert ctx.stage_errors and ctx.source_status == SourceStatus.CONFIRMED  # strong title keyword coverage
    untitled = await correspond(make_context(CLAIM, articles=[article(None, BODY)]))
    assert untitled.analysis.metrics["headline_title_similarity"].reason == "source article has no title"


async def test_verified_sources_mode_never_names_a_claimed_source():
    ctx = make_context(CLAIM, search_adequate=True)
    ctx.verification_mode = source_policy.VERIFIED_SOURCES
    out = await correspond(ctx)
    assert out.source_status == SourceStatus.NOT_FOUND
    assert "verified sources searched" in out.analysis.source_basis[0] and "claimed source" not in out.analysis.source_basis[0]
