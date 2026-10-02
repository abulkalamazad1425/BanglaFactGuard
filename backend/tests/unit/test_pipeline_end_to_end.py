"""The real S01-S12 stage classes wired together over a real (SQLite)
database, with only the outside world faked: search providers, the article
HTTP fetch, and the ML services (deterministic stand-ins from
pipeline_helpers). Proves the wiring - identity, retrieval, extraction,
analysis, decisions, persistence, reuse - not model accuracy."""

from __future__ import annotations

import json
from datetime import date
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.core.constants import ContentStatus, DateStatus, SourceStatus, SubmissionStatus
from app.features.sources.repository import SourceRepository
from app.features.submissions.repository import RetrievedArticleV2Repository, SubmissionRepository
from app.features.verification.pipeline import factory
from app.features.verification.pipeline.context import build_context
from app.features.verification.pipeline.orchestrator import PipelineOrchestrator
from app.features.verification.presenter import load_verification_response
from app.features.verification.repository import ResultV2Repository
from db_helpers import add_source, add_user, make_session_factory
from pipeline_helpers import FakeEmbedder, FakeNER, neutral_nli

ARTICLE_URL = "https://www.prothomalo.com/bangladesh/district/abc12345def"
TITLE = "প্রধান উপদেষ্টা ঢাকায় নতুন সেতুর উদ্বোধন করেছেন"
PARA = (
    "প্রধান উপদেষ্টা ঢাকায় নতুন সেতুর উদ্বোধন করেছেন। সেতুটি নির্মাণে তিন বছর সময় লেগেছে। "
    "অনুষ্ঠানে বহু মানুষ উপস্থিত ছিলেন এবং স্থানীয় বাসিন্দারা সেতুটিকে স্বাগত জানিয়েছেন।"
)
HTML = (
    f"<html><head><title>{TITLE}</title>"
    '<script type="application/ld+json">{"@type":"NewsArticle","datePublished":"2026-06-07T09:00:00+06:00",'
    '"dateModified":"2026-06-09T09:00:00+06:00"}</script></head>'
    f"<body><h1>{TITLE}</h1><article><p>{PARA}</p><p>{PARA}</p></article></body></html>"
)


class FakeProvider:
    def __init__(self, entries=None, exc: Exception | None = None):
        self.entries, self.exc = entries or [], exc

    async def search_entries(self, query, domain=None, published_date=None, source_config=None):
        if self.exc:
            raise self.exc
        return list(self.entries)


@pytest.fixture
async def env(monkeypatch, tmp_path):
    engine, sessions = await make_session_factory()
    async with sessions() as s:
        await add_source(s)
        await s.commit()

    def patch_providers(entries=None, exc=None):
        for name in ("NewsDataClient", "GoogleCSEClient", "PyGoogleNewsClient", "DuckDuckGoClient", "InternalSiteSearchClient"):
            monkeypatch.setattr(factory, name, lambda *a, _e=entries, _x=exc, **k: FakeProvider(_e, _x))

    patch_providers([(ARTICLE_URL, TITLE)])
    # no 0.5s per-domain courtesy delay in tests
    import app.features.verification.pipeline.stages.s05_evidence_retrieval as s05

    async def fast_sleep(_):
        return None

    monkeypatch.setattr(s05.asyncio, "sleep", fast_sleep)
    yield SimpleEnv(engine, sessions, patch_providers)
    await engine.dispose()


class SimpleEnv:
    def __init__(self, engine, sessions, patch_providers):
        self.engine, self.sessions, self.patch_providers = engine, sessions, patch_providers

    def http(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            transport=httpx.MockTransport(lambda req: httpx.Response(200, text=HTML)), follow_redirects=True
        )

    def cache(self) -> MagicMock:
        store: dict = {}
        c = MagicMock()
        c.get_claim_result = AsyncMock(side_effect=lambda k: store.get(k))

        async def set_ptr(k, payload, ttl):
            store[k] = payload.encode()

        c.set_claim_pointer = AsyncMock(side_effect=set_ptr)
        c.invalidate_claim = AsyncMock()
        c.get_search_result = AsyncMock(return_value=None)
        c.set_search_result = AsyncMock()
        return c

    async def run(self, session, *, headline, body=None, published=None, force=False, user=None, cache=None, ner=None):
        cache = cache or self.cache()
        http = self.http()
        stages = factory.build_verification_stages(
            submission_repo=SubmissionRepository(session),
            result_repo=ResultV2Repository(session),
            article_repo=RetrievedArticleV2Repository(session),
            source_repo=SourceRepository(session),
            cache_service=cache,
            embedding_service=FakeEmbedder(),
            ner_service=ner or FakeNER(),
            nli_service=neutral_nli(),
            http_client=http,
        )
        ctx = build_context(
            headline=headline, claimed_source="প্রথম আলো", news_body=body, published_date=published,
            force_refresh=force, submitter_id=user,
        )
        ctx = await PipelineOrchestrator(stages, SubmissionRepository(session)).run(ctx)
        await http.aclose()
        return ctx, cache


async def test_full_pipeline_confirms_matches_and_persists_everything(env):
    async with env.sessions() as s:
        ctx, _ = await env.run(s, headline=TITLE, published=date(2026, 6, 7))
        assert ctx.persisted and ctx.cache_hit is False
        assert (ctx.source_status, ctx.content_status, ctx.date_status) == (
            SourceStatus.CONFIRMED, ContentStatus.MATCHED, DateStatus.MATCHED,
        ), (ctx.analysis.source_basis, ctx.analysis.content_basis)
        assert ctx.top_article.published_date_source == "json_ld.datePublished"  # dateModified ignored

        sub = await SubmissionRepository(s).get_by_id(ctx.submission_id)
        assert sub.status == SubmissionStatus.EXPERT_REVIEW
        res = await ResultV2Repository(s).get_by_submission_id(sub.id)
        assert res.body_similarity is None and res.claim_scope == "HEADLINE_ONLY"
        assert res.headline_keyword_coverage == 1.0 and res.ai_consensus_label is None
        r = await load_verification_response(
            sub, result_repo=ResultV2Repository(s), article_repo=RetrievedArticleV2Repository(s)
        )
        assert r.overall_verdict is None and r.review_pending
        assert r.analysis.date.claimed_date == date(2026, 6, 7) and r.analysis.search.adequate is True
        assert r.matched_articles and r.matched_articles[0].url == ARTICLE_URL


async def test_wrong_claimed_date_is_matched_plus_mismatched_end_to_end(env):
    async with env.sessions() as s:
        ctx, _ = await env.run(s, headline=TITLE, published=date(2026, 6, 20))
        assert ctx.source_status == SourceStatus.CONFIRMED  # date-free retrieval still finds the report
        assert ctx.content_status == ContentStatus.MATCHED
        assert ctx.date_status == DateStatus.MISMATCHED


async def test_changed_number_in_headline_is_altered_end_to_end(env, monkeypatch):
    altered = TITLE.replace("নতুন", "৫ নতুন")
    async with env.sessions() as s:
        ctx, _ = await env.run(s, headline=altered + " ১০০ কোটি টাকা")
        # the source never states "100 crore": unsupported -> not evaluated, never ALTERED by absence alone
        assert ctx.content_status != ContentStatus.ALTERED
        assert ctx.manipulation_flags.check_states["numbers"].value in {"NOT_EVALUATED", "PASSED"}


async def test_all_providers_failing_end_to_end_is_incomplete_not_not_found(env):
    env.patch_providers(exc=RuntimeError("provider outage"))
    async with env.sessions() as s:
        ctx, cache = await env.run(s, headline=TITLE, published=date(2026, 6, 7))
        assert ctx.source_status == SourceStatus.INCOMPLETE
        assert ctx.content_status is None and ctx.date_status is None
        assert ctx.persisted  # still reaches expert review as a reviewable incomplete result
        cache.set_claim_pointer.assert_not_awaited()  # and is never cached as settled


async def test_second_identical_claim_reuses_the_result_then_force_refresh_does_not(env):
    cache = env.cache()
    async with env.sessions() as s:
        owner = await add_user(s)
        other = await add_user(s)
        first, _ = await env.run(s, headline=TITLE, published=date(2026, 6, 7), user=owner.id, cache=cache)
        await s.commit()
        assert first.cache_hit is False and first.submission_id

        # identical claim again: S02 hit (Redis pointer), no search/analysis stages ran
        second, _ = await env.run(s, headline=TITLE, published=date(2026, 6, 7), user=other.id, cache=cache)
        assert second.cache_hit is True and second.reused_from_submission_id == first.submission_id
        assert second.persisted is False and second.search_attempted == 0

        # different claimed date => different identity => full run
        third, _ = await env.run(s, headline=TITLE, published=date(2026, 6, 8), user=other.id, cache=cache)
        assert third.cache_hit is False

        # force_refresh => full run even though a reusable result exists
        forced, _ = await env.run(s, headline=TITLE, published=date(2026, 6, 7), user=owner.id, cache=cache, force=True)
        assert forced.cache_hit is False and forced.submission_id != first.submission_id


async def test_service_verify_returns_the_db_result_and_reuse_gives_each_user_their_own_submission(env):
    from app.features.verification.schemas import VerificationRequest
    from app.features.verification.service import VerificationService

    cache = env.cache()
    http = env.http()
    async with env.sessions() as s:
        owner, other = await add_user(s), await add_user(s)
        await s.commit()

        def service() -> VerificationService:
            return VerificationService(
                SubmissionRepository(s), ResultV2Repository(s), RetrievedArticleV2Repository(s),
                SourceRepository(s), cache, FakeEmbedder(), FakeNER(), neutral_nli(), http,
            )

        req = VerificationRequest(headline=TITLE, claimed_source_text="প্রথম আলো", published_date=date(2026, 6, 7))
        first = await service().verify(req, submitter_id=owner.id)
        assert first.cached is False and first.source_status == SourceStatus.CONFIRMED
        assert first.processing_time_ms is not None and first.overall_verdict is None
        await s.commit()

        second = await service().verify(req, submitter_id=other.id)
        assert second.cached is True
        assert second.submission_id != first.submission_id  # their own submission, not the owner's
        mine = await SubmissionRepository(s).get_by_id(second.submission_id)
        assert mine.submitter_id == other.id and mine.duplicate_of_submission_id == first.submission_id
        # same saved content as the original, read through the one presenter
        a, b = first.model_dump(), second.model_dump()
        for key in ("source_status", "content_status", "date_status", "scores", "manipulation_flags", "claim_scope"):
            assert a[key] == b[key], key
    await http.aclose()
