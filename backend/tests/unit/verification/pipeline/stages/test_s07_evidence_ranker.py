"""S07: retrieval relevance. The article whose headline IS the claim must win;
the cross-encoder only breaks near-ties."""

from __future__ import annotations

from app.features.verification import source_policy
from app.features.verification.pipeline.stages.s07_evidence_ranker import EvidenceRankerStage
from tests.helpers.pipeline import FakeEmbedder, article, make_context

CLAIM = "জঙ্গল সলিমপুরে সারদার আদলে পুলিশ একাডেমি হচ্ছে"
REWORDED = "সলিমপুরে সারদার আদলে পুলিশ একাডেমি, কারাগারও হবে"
UNRELATED = "চট্টগ্রাম বন্দরে নতুন জাহাজ ভিড়েছে"
BODY = "জঙ্গল সলিমপুরে সারদার আদলে পুলিশ একাডেমি হচ্ছে বলে জানিয়েছেন স্বরাষ্ট্রমন্ত্রী।"


class SaturatedCrossEncoder:
    """Scores that slightly favour a re-worded video page, as observed on the
    real Prothom Alo case (+10.87 vs +10.79)."""

    async def scores(self, claim, articles):
        return [10.9 if "/video/" in a.url else 10.7 for a in articles]


def stage(embedder=None, reranker=None) -> EvidenceRankerStage:
    s = EvidenceRankerStage(embedding_service=embedder or FakeEmbedder())
    s._reranker = reranker or SaturatedCrossEncoder()
    return s


async def test_the_exact_headline_wins_and_the_cross_encoder_only_breaks_ties():
    reworded = article(REWORDED, BODY, url="https://www.prothomalo.com/video/bangladesh/x1")
    exact = article(CLAIM, BODY, url="https://www.prothomalo.com/bangladesh/x2")
    others = [article(UNRELATED, url=f"https://www.prothomalo.com/bangladesh/y{i}") for i in range(3)]
    ctx = await stage().execute(make_context(CLAIM, articles=[reworded, exact, *others]))
    assert ctx.top_article.url == exact.url and len(ctx.ranked_articles) > 3
    assert all(0.0 <= a.rank_score <= 1.0 for a in ctx.ranked_articles)


async def test_a_kicker_line_and_the_claimed_domain_count_toward_relevance():
    kicker = article("রায় দ্রুত কার্যকরের দাবি", url="https://www.prothomalo.com/a/1")
    kicker = kicker.model_copy(update={"title_variants": [CLAIM]})
    off_domain = article(CLAIM, url="https://www.othernews.com/a/2")
    ranked = (await stage().execute(make_context(CLAIM, articles=[off_domain, kicker]))).ranked_articles
    assert [a.url for a in ranked] == [kicker.url, off_domain.url]


async def test_verified_sources_give_every_eligible_publisher_the_same_bonus():
    ctx = make_context(CLAIM, articles=[article(CLAIM, url="https://www.unlisted.com/a/1"),
                                       article(CLAIM, url="https://www.jugantor.com/a/1")])
    ctx.verification_mode = source_policy.VERIFIED_SOURCES
    ctx.verified_scope = source_policy.VerifiedScope([source_policy.VerifiedPublisher("jugantor.com", "j", ["jugantor.com"], {})])
    assert (await stage().execute(ctx)).top_article.url == "https://www.jugantor.com/a/1"


async def test_weak_or_unmeasurable_evidence_still_yields_the_best_candidate(monkeypatch):
    s = stage(embedder=FakeEmbedder(fail=True))
    monkeypatch.setattr(s, "_min_score", 5.0)  # nothing reaches the minimum
    untitled = article(None, BODY, url="https://www.prothomalo.com/a/3")
    ctx = await s.execute(make_context(CLAIM, articles=[article(UNRELATED, url="https://x.com/a/1"), untitled]))
    assert [a.url for a in ctx.ranked_articles] == [untitled.url]
    empty = await stage().execute(make_context(CLAIM))
    assert empty.ranked_articles == [] and empty.top_article is None
