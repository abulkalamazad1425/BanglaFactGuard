"""Retrieval robustness: the exact-headline article wins the ranking, a matching
search result that could not be fetched is never reported as NOT_FOUND,
kicker headlines count, multi-outlet search results are ranked by relevance,
and an anti-bot-walled host is backed off from."""

from __future__ import annotations

from bs4 import BeautifulSoup

from app.core.constants import ContentStatus, SearchProvider, SourceStatus
from app.features.articles.schemas import CandidateArticleSchema
from app.features.verification.analysis.decisions import Correspondence, decide_source
from app.features.verification.pipeline.stages import s05_evidence_retrieval as s05
from app.features.verification.pipeline.stages.s04_source_search import _cached_entries, _title_relevance
from app.features.verification.pipeline.stages.s06_article_extractor import _headline_variants
from app.features.verification.pipeline.stages.s07_evidence_ranker import EvidenceRankerStage
from tests.unit.pipeline_helpers import FakeEmbedder, article, make_context, run_analysis

CLAIM = "জঙ্গল সলিমপুরে সারদার আদলে পুলিশ একাডেমি হচ্ছে"
REWORDED = "সলিমপুরে সারদার আদলে পুলিশ একাডেমি, কারাগারও হবে"  # STRONG on its own, not identical
LOOSE = "জঙ্গল সলিমপুরে পুলিশ একাডেমি ও কারাগার তৈরি করা হবে"  # PLAUSIBLE only
BODY = "জঙ্গল সলিমপুরে সারদার আদলে পুলিশ একাডেমি হচ্ছে বলে জানিয়েছেন স্বরাষ্ট্রমন্ত্রী।"
UNRELATED = "চট্টগ্রাম বন্দরে নতুন জাহাজ ভিড়েছে"


def candidate(url: str, title: str | None, position: int = 1) -> CandidateArticleSchema:
    return CandidateArticleSchema(
        url=url, title_snippet=title, search_provider=SearchProvider.PY_GOOGLE_NEWS,
        query_type="headline", position=position,
    )


# ── false NOT_FOUND ──────────────────────────────────────────────────────

def test_a_blocked_matching_result_makes_the_source_incomplete_not_absent():
    status, basis = decide_source(has_evidence=False, search_adequate=True, retrieval_failed=False,
                                  correspondence=None, blocked_match="kalerkantho.com")
    assert status == SourceStatus.INCOMPLETE
    assert "blocked automated access" in basis[-1]
    status, _ = decide_source(has_evidence=True, search_adequate=True, retrieval_failed=False,
                              correspondence=Correspondence("NONE", []), blocked_match="kalerkantho.com")
    assert status == SourceStatus.INCOMPLETE
    # Without a blocked match, a read report confirms and absence stands.
    assert decide_source(has_evidence=True, search_adequate=True, retrieval_failed=False,
                         correspondence=Correspondence("PLAUSIBLE", []))[0] == SourceStatus.CONFIRMED
    assert decide_source(has_evidence=True, search_adequate=True, retrieval_failed=False,
                         correspondence=Correspondence("NONE", []))[0] == SourceStatus.NOT_FOUND


async def test_a_blocked_exact_report_is_not_replaced_by_a_weaker_stand_in():
    """The exact report was found but blocked; another outlet's loosely related
    article was read. That must not become CONFIRMED with an ALTERED headline."""
    blocked_url = "https://www.kalerkantho.com/online/dhaka/2026/10/09/1750312"
    loose = article(LOOSE, BODY, url="https://dailyinqilab.com/national/news/947665")
    ctx = make_context(CLAIM, articles=[loose])
    ctx.candidate_urls = [candidate(blocked_url, f"{CLAIM} - কালের কণ্ঠ")]
    ctx.failed_extraction_urls = [blocked_url]
    ctx = await run_analysis(ctx)
    assert ctx.source_status == SourceStatus.INCOMPLETE


async def test_a_blocked_result_does_not_override_an_exact_report_that_was_read():
    blocked_url = "https://www.kalerkantho.com/online/dhaka/2026/10/09/1750312"
    exact = article(CLAIM, BODY, url="https://dailynayadiganta.com/post/national/1059596")
    ctx = make_context(CLAIM, articles=[exact])
    ctx.candidate_urls = [candidate(blocked_url, f"{CLAIM} - কালের কণ্ঠ")]
    ctx.failed_extraction_urls = [blocked_url]
    ctx = await run_analysis(ctx)
    assert ctx.source_status == SourceStatus.CONFIRMED
    assert ctx.content_status == ContentStatus.MATCHED


async def test_s08_reports_incomplete_when_the_matching_search_result_was_blocked():
    blocked_url = "https://www.kalerkantho.com/online/national/2026/10/08/1750100"
    ctx = make_context(CLAIM, articles=[article(UNRELATED, url="https://prothomalo.com/a/9")])
    ctx.candidate_urls = [candidate(blocked_url, f"{CLAIM} - কালের কণ্ঠ"),
                          candidate("https://prothomalo.com/a/9", UNRELATED, 2)]
    ctx.failed_extraction_urls = [blocked_url]
    ctx = await run_analysis(ctx)
    assert ctx.source_status == SourceStatus.INCOMPLETE
    assert any("blocked automated access" in b for b in ctx.analysis.source_basis)


async def test_s08_keeps_not_found_when_only_unrelated_results_were_blocked():
    blocked_url = "https://www.kalerkantho.com/online/national/2026/10/08/1"
    ctx = make_context(CLAIM, articles=[article(UNRELATED, url="https://prothomalo.com/a/9")])
    ctx.candidate_urls = [candidate(blocked_url, "ক্রিকেট দলের নতুন অধিনায়ক ঘোষণা - কালের কণ্ঠ")]
    ctx.failed_extraction_urls = [blocked_url]
    ctx = await run_analysis(ctx)
    assert ctx.source_status == SourceStatus.NOT_FOUND


# ── ranking: the exact headline wins ─────────────────────────────────────

async def test_s08_picks_the_exact_headline_over_an_earlier_ranked_rewording():
    reworded = article(REWORDED, BODY, url="https://www.prothomalo.com/video/bangladesh/x1")
    exact = article(CLAIM, BODY, url="https://dailynayadiganta.com/post/national/1059596")
    ctx = await run_analysis(make_context(CLAIM, articles=[reworded, exact]))
    assert ctx.source_status == SourceStatus.CONFIRMED
    assert ctx.top_article.url == exact.url
    assert ctx.content_status == ContentStatus.MATCHED


class _CrossEncoderPrefersVideo:
    """Saturated scores that slightly favour the re-worded video page, as
    observed on the real Prothom Alo case (+10.87 vs +10.79)."""

    async def scores(self, claim, articles):
        return [10.9 if "/video/" in a.url else 10.7 for a in articles]

    async def rerank(self, claim, articles, top_k=5):  # the pre-fix interface
        order = await self.scores(claim, articles)
        return [a for _, a in sorted(zip(order, articles), key=lambda x: -x[0])][:top_k]


async def test_s07_cross_encoder_only_breaks_ties():
    # Same outlet throughout (the claimed one), so all five pass the minimum
    # score and the cross-encoder is consulted.
    reworded = article(REWORDED, BODY, url="https://www.prothomalo.com/video/bangladesh/x1")
    exact = article(CLAIM, BODY, url="https://www.prothomalo.com/bangladesh/x2")
    others = [article(UNRELATED, url=f"https://www.prothomalo.com/bangladesh/y{i}") for i in range(3)]
    ctx = make_context(CLAIM, articles=[reworded, exact, *others])
    stage = EvidenceRankerStage(embedding_service=FakeEmbedder())
    stage._reranker = _CrossEncoderPrefersVideo()
    ctx = await stage.execute(ctx)
    assert len(ctx.ranked_articles) > 3
    assert ctx.top_article.url == exact.url
    assert all(0.0 <= a.rank_score <= 1.0 for a in ctx.ranked_articles)


# ── kicker headlines ─────────────────────────────────────────────────────

KICKER_HTML = """<div class="p-6">
  <h2 class="text-red-600">প্রধানমন্ত্রীর সঙ্গে আবরার ফাহাদের পরিবারের সাক্ষাৎ</h2>
  <h1>রায় দ্রুত কার্যকরের দাবি</h1>
  <div>স্টাফ রিপোর্টার</div>
</div>"""


def test_s06_reads_the_kicker_printed_above_the_title():
    soup = BeautifulSoup(KICKER_HTML, "html.parser")
    assert _headline_variants(soup, "রায় দ্রুত কার্যকরের দাবি") == [
        "প্রধানমন্ত্রীর সঙ্গে আবরার ফাহাদের পরিবারের সাক্ষাৎ",
        "প্রধানমন্ত্রীর সঙ্গে আবরার ফাহাদের পরিবারের সাক্ষাৎ রায় দ্রুত কার্যকরের দাবি",
    ]
    # A heading that is a link (e.g. "related news") is not a kicker.
    linked = BeautifulSoup('<div><h1>শিরোনাম এখানে</h1><h2><a href="/x">আরও খবর পড়ুন এখানে</a></h2></div>',
                           "html.parser")
    assert _headline_variants(linked, "শিরোনাম এখানে") == []


async def test_a_claim_quoting_the_kicker_matches_its_article():
    kicker = "প্রধানমন্ত্রীর সঙ্গে আবরার ফাহাদের পরিবারের সাক্ষাৎ"
    page = article("রায় দ্রুত কার্যকরের দাবি", "আবরার ফাহাদের পরিবার প্রধানমন্ত্রীর সঙ্গে সাক্ষাৎ করেছে।",
                   url="https://www.mzamin.com/article/47841")
    page = page.model_copy(update={"title_variants": [kicker, f"{kicker} রায় দ্রুত কার্যকরের দাবি"]})
    ctx = await run_analysis(make_context(kicker, articles=[page]))
    assert ctx.source_status == SourceStatus.CONFIRMED
    assert ctx.top_article.title == kicker
    assert ctx.content_status == ContentStatus.MATCHED
    # Pipeline-internal: never serialised into API responses.
    assert "title_variants" not in page.model_dump()


# ── multi-outlet search results ──────────────────────────────────────────

def test_search_titles_rank_relevance_and_cached_results_keep_titles():
    assert _title_relevance(CLAIM, f"{CLAIM} - নয়া দিগন্ত") == 1.0
    assert _title_relevance(CLAIM, "ক্রিকেট দলের নতুন অধিনায়ক - সমকাল") == 0.0
    assert _title_relevance(CLAIM, None) is None
    assert _cached_entries([["https://a/1", "t"], "https://a/2", ["https://a/3", None]]) == [
        ("https://a/1", "t"), ("https://a/2", None), ("https://a/3", None),
    ]


# ── anti-bot back-off ────────────────────────────────────────────────────

def test_a_walled_host_is_left_alone_for_a_while(monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(s05.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(s05, "_walled_until", {})
    url = "https://bangla.thedailystar.net/news/bangladesh/news-1"
    assert not s05._host_cooling_down(url)
    s05._mark_walled(url)
    assert s05._host_cooling_down("https://bangla.thedailystar.net/news/other-2")
    assert not s05._host_cooling_down("https://samakal.com/bangladesh/article/1")
    now[0] += s05._WALL_COOLDOWN_S + 1
    assert not s05._host_cooling_down(url)
