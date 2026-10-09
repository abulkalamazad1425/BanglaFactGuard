"""VERIFIED_SOURCES mode: a claim with no / an unrecognised / an inactive
source is checked against the active verified sources (Google only,
domain-restricted), while the claimed-source path stays exactly as it was.

Real S01-S13 stages over SQLite; only search, HTTP and ML are faked."""

from __future__ import annotations

import uuid
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.core.constants import ClaimScope, ContentStatus, SourceStatus
from app.features.sources.repository import SourceRepository
from app.features.submissions.repository import RetrievedArticleRepository, SubmissionRepository
from app.features.verification import source_policy
from app.features.verification.pipeline import factory
from app.features.verification.pipeline.context import build_context
from app.features.verification.pipeline.orchestrator import PipelineOrchestrator
from app.features.verification.presenter import load_verification_response
from app.features.verification.repository import ResultRepository
from app.shared.utils.hashing import compute_claim_hash
from db_helpers import add_source, make_session_factory
from pipeline_helpers import FakeEmbedder, FakeNER, FakeNLI

TITLE = "প্রধান উপদেষ্টা ঢাকায় নতুন সেতুর উদ্বোধন করেছেন"
PARA = (
    "প্রধান উপদেষ্টা ঢাকায় নতুন সেতুর উদ্বোধন করেছেন। সেতুটি নির্মাণে তিন বছর সময় লেগেছে। "
    "অনুষ্ঠানে বহু মানুষ উপস্থিত ছিলেন এবং স্থানীয় বাসিন্দারা সেতুটিকে স্বাগত জানিয়েছেন।"
)
HTML = (
    f"<html><head><title>{TITLE}</title>"
    '<script type="application/ld+json">{"@type":"NewsArticle","datePublished":"2026-06-07T09:00:00+06:00"}</script>'
    f"</head><body><h1>{TITLE}</h1><article><p>{PARA}</p><p>{PARA}</p></article></body></html>"
)
JUGANTOR_URL = "https://www.jugantor.com/national/123456"
OFF_LIST_URL = "https://www.unknown-news.com/national/123456"
DECEPTIVE_URL = "https://www.jugantor.com.evil.net/national/123456"


class RecordingProvider:
    def __init__(self, entries=None, exc: Exception | None = None):
        self.entries, self.exc = entries or [], exc
        self.queries: list[str] = []

    async def search_entries(self, query, domain=None, published_date=None, source_config=None):
        self.queries.append(query)
        if self.exc:
            raise self.exc
        return list(self.entries)


class Env:
    def __init__(self, monkeypatch, sessions):
        self.monkeypatch, self.sessions = monkeypatch, sessions
        self.fetched: list[str] = []
        self.set_providers(google=RecordingProvider([(JUGANTOR_URL, TITLE)]))

    def set_providers(self, *, google, internal=None):
        self.google = google
        self.internal = internal or RecordingProvider()
        self.monkeypatch.setattr(factory, "PyGoogleNewsClient", lambda *a, **k: self.google)
        self.monkeypatch.setattr(factory, "InternalSiteSearchClient", lambda *a, **k: self.internal)

    def http(self) -> httpx.AsyncClient:
        def handler(req):
            self.fetched.append(str(req.url))
            return httpx.Response(200, text=HTML)

        return httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=True)

    @staticmethod
    def cache() -> MagicMock:
        store: dict = {}
        c = MagicMock()
        c.get_claim_result = AsyncMock(side_effect=lambda k: store.get(k))

        async def set_ptr(k, payload, ttl):
            store[k] = payload.encode()

        c.set_claim_pointer = AsyncMock(side_effect=set_ptr)
        c.invalidate_claim = AsyncMock(side_effect=lambda k: store.pop(k, None))
        c.get_search_result = AsyncMock(return_value=None)
        c.set_search_result = AsyncMock()
        return c

    async def run(self, session, *, source="", headline=TITLE, published=None, cache=None):
        http = self.http()
        stages = factory.build_verification_stages(
            submission_repo=SubmissionRepository(session),
            result_repo=ResultRepository(session),
            article_repo=RetrievedArticleRepository(session),
            source_repo=SourceRepository(session),
            cache_service=cache or self.cache(),
            embedding_service=FakeEmbedder(),
            ner_service=FakeNER(),
            nli_service=FakeNLI(),
            http_client=http,
        )
        ctx = build_context(headline=headline, claimed_source=source, published_date=published)
        ctx = await PipelineOrchestrator(stages, SubmissionRepository(session)).run(ctx)
        await http.aclose()
        return ctx


@pytest.fixture
async def env(monkeypatch):
    engine, sessions = await make_session_factory()
    async with sessions() as s:
        await add_source(s)  # prothomalo.com (has no internal search configured here)
        jug = await add_source(s, "jugantor.com")
        jug.display_name = "যুগান্তর"
        jug.aliases = ["যুগান্তর"]
        await s.commit()
    import app.features.verification.pipeline.stages.s05_evidence_retrieval as s05

    async def fast_sleep(_):
        return None

    monkeypatch.setattr(s05.asyncio, "sleep", fast_sleep)
    yield Env(monkeypatch, sessions)
    await engine.dispose()


async def test_no_source_searches_verified_sources_with_google_only(env):
    async with env.sessions() as s:
        ctx = await env.run(s, source="", published=date(2026, 6, 7))
        assert ctx.verification_mode == source_policy.VERIFIED_SOURCES
        assert ctx.source_resolution_reason == source_policy.REASON_NOT_SUPPLIED
        assert env.internal.queries == []  # internal-site provider never dispatched
        assert env.google.queries and all(
            "site:jugantor.com" in q and "site:prothomalo.com" in q and " OR " in q for q in env.google.queries
        )
        # bounded: phrasings x domain groups, never phrasings x sources x ...
        assert len(env.google.queries) <= 3
        assert ctx.source_status == SourceStatus.CONFIRMED
        assert ctx.content_status == ContentStatus.MATCHED
        assert ctx.analysis.headline_alteration.source_publisher == "jugantor.com"
        scope = ctx.analysis.source_scope
        assert scope.verification_mode == "VERIFIED_SOURCES" and scope.claimed_source is None
        assert scope.primary_article_url == JUGANTOR_URL and scope.primary_publisher == "jugantor.com"
        assert set(scope.eligible_publishers) == {"jugantor.com", "prothomalo.com"}

        sub = await SubmissionRepository(s).get_by_id(ctx.submission_id)
        assert sub.claimed_source_text is None
        r = await load_verification_response(
            sub, result_repo=ResultRepository(s), article_repo=RetrievedArticleRepository(s)
        )
        assert r.verification_mode == "VERIFIED_SOURCES"
        assert r.source_resolution_reason == "SOURCE_NOT_SUPPLIED"
        assert r.matched_articles[0].is_primary and r.matched_articles[0].publisher == "jugantor.com"
        assert "verified" in r.reasoning.lower()


async def test_off_list_and_deceptive_hosts_are_never_fetched(env):
    env.set_providers(google=RecordingProvider([(OFF_LIST_URL, TITLE), (DECEPTIVE_URL, TITLE), (JUGANTOR_URL, TITLE)]))
    async with env.sessions() as s:
        ctx = await env.run(s, source="")
        assert [c.url for c in ctx.candidate_urls] == [JUGANTOR_URL]
        assert all("unknown-news" not in u and "evil.net" not in u for u in env.fetched)
        assert ctx.source_status == SourceStatus.CONFIRMED


async def test_unrecognised_source_text_falls_back_and_is_kept_as_provenance(env):
    async with env.sessions() as s:
        ctx = await env.run(s, source="সম্পূর্ণ অচেনা পত্রিকা")
        assert ctx.verification_mode == source_policy.VERIFIED_SOURCES
        assert ctx.source_resolution_reason == source_policy.REASON_UNRECOGNIZED
        assert ctx.analysis.source_scope.raw_source_text == "সম্পূর্ণ অচেনা পত্রিকা"


async def test_inactive_source_falls_back(env):
    async with env.sessions() as s:
        jug = await SourceRepository(s).get_by_canonical_name("jugantor.com")
        jug.is_active = False
        await s.commit()
        ctx = await env.run(s, source="jugantor.com")
        assert ctx.verification_mode == source_policy.VERIFIED_SOURCES
        assert ctx.source_resolution_reason == source_policy.REASON_INACTIVE
        # an inactive publisher is not in the evidence scope either
        assert [p.canonical for p in ctx.verified_scope.publishers] == ["prothomalo.com"]
        assert ctx.source_status != SourceStatus.CONFIRMED  # only a jugantor URL came back


async def test_claimed_source_path_is_unchanged(env):
    env.set_providers(
        google=RecordingProvider([("https://www.prothomalo.com/bangladesh/abc12345", TITLE)]),
    )
    async with env.sessions() as s:
        ctx = await env.run(s, source="প্রথম আলো")
        assert ctx.verification_mode == source_policy.CLAIMED_SOURCE
        assert ctx.normalized_source == "prothomalo.com"
        assert all(q.startswith("site:prothomalo.com ") and " OR " not in q for q in env.google.queries)
        # the identity of a claimed-source claim is byte-for-byte what it always was
        assert ctx.content_hash == compute_claim_hash(TITLE, "prothomalo.com", ClaimScope.HEADLINE_ONLY)
        assert ctx.source_status == SourceStatus.CONFIRMED


async def test_google_failure_is_incomplete_never_not_found(env):
    env.set_providers(google=RecordingProvider(exc=RuntimeError("google down")))
    async with env.sessions() as s:
        ctx = await env.run(s, source="")
        assert ctx.source_status == SourceStatus.INCOMPLETE
        assert ctx.analysis.source_scope.incomplete_reason


async def test_adequate_empty_search_is_not_found(env):
    env.set_providers(google=RecordingProvider([]))
    async with env.sessions() as s:
        ctx = await env.run(s, source="")
        assert ctx.source_status == SourceStatus.NOT_FOUND
        assert "verified sources searched" in ctx.reasoning


async def test_empty_registry_is_incomplete_and_searches_nothing(env):
    async with env.sessions() as s:
        for name in ("prothomalo.com", "jugantor.com"):
            (await SourceRepository(s).get_by_canonical_name(name)).is_active = False
        await s.commit()
        ctx = await env.run(s, source="")
        assert env.google.queries == [] and env.fetched == []
        assert ctx.source_status == SourceStatus.INCOMPLETE
        assert "No active verified sources" in ctx.analysis.source_scope.incomplete_reason


async def test_fallback_and_claimed_results_are_never_reused_for_each_other(env):
    async with env.sessions() as s:
        cache = env.cache()
        first = await env.run(s, source="", cache=cache)
        await s.commit()
        again = await env.run(s, source="   ", cache=cache)  # blank == missing
        assert again.cache_hit and again.reused_from_submission_id == first.submission_id

        env.set_providers(google=RecordingProvider([("https://www.prothomalo.com/bangladesh/abc12345", TITLE)]))
        claimed = await env.run(s, source="প্রথম আলো", cache=cache)
        assert claimed.cache_hit is False
        assert claimed.content_hash != first.content_hash


async def test_registry_change_starts_a_new_verification_context(env):
    async with env.sessions() as s:
        before = await source_policy.load_verified_scope(SourceRepository(s))
        (await SourceRepository(s).get_by_canonical_name("jugantor.com")).is_active = False
        await s.commit()
        after = await source_policy.load_verified_scope(SourceRepository(s))
        assert before.fingerprint != after.fingerprint
        assert source_policy.verified_identity_key(before) != source_policy.verified_identity_key(after)


async def test_fallback_disabled_restores_the_rejection(env, monkeypatch):
    from app.core.exceptions import PipelineError

    monkeypatch.setattr(source_policy, "fallback_enabled", lambda: False)
    async with env.sessions() as s:
        with pytest.raises(PipelineError):
            await env.run(s, source="")
        assert env.google.queries == []


# ── presenter: primary article first even beyond rank 3; max three unique ──


async def test_presenter_shows_primary_first_even_when_ranked_below_three():
    sub_id = uuid.uuid4()
    primary_id = uuid.uuid4()

    def art(url, rank, aid=None, ok=True):
        return SimpleNamespace(
            id=aid or uuid.uuid4(), url=url, title=url, author=None, published_date=None, body="b",
            rank_score=rank, extraction_method=None, extraction_success=ok,
        )

    articles = [
        art("https://www.jugantor.com/a", 0.9),
        art("https://www.jugantor.com/a/", 0.85),  # duplicate URL
        art("https://www.prothomalo.com/b", 0.8),
        art("https://www.prothomalo.com/c", 0.7),
        art("https://www.jugantor.com/primary", 0.4, primary_id),
    ]
    result = SimpleNamespace(
        source_status=SourceStatus.CONFIRMED, content_status=ContentStatus.MATCHED, date_status=None,
        overall_verdict=None, reused_from_submission_id=None, top_article_id=primary_id,
        claim_scope="HEADLINE_ONLY", headline_check_status="COMPLETED", headline_exact_match=True,
        confidence=0.9, reasoning="r", avg_verification_time_ms=1, created_at="2026-01-01T00:00:00",
        pipeline_version="v", analysis_details={
            "source_scope": {"verification_mode": "VERIFIED_SOURCES",
                             "eligible_publishers": ["jugantor.com", "prothomalo.com"]},
        },
        submission_id=sub_id,
    )
    submission = SimpleNamespace(
        id=sub_id, submission_type="SOURCE_BASED", body_text=None, headline="h",
        published_date=None, claimed_source_text=None, duplicate_of_submission_id=None,
    )
    result_repo = MagicMock()
    result_repo.get_by_submission_id = AsyncMock(return_value=result)
    article_repo = MagicMock()
    article_repo.get_for_submission = AsyncMock(return_value=articles)

    r = await load_verification_response(submission, result_repo=result_repo, article_repo=article_repo)
    urls = [a.url for a in r.matched_articles]
    assert urls == ["https://www.jugantor.com/primary", "https://www.jugantor.com/a", "https://www.prothomalo.com/b"]
    assert r.matched_articles[0].is_primary and not r.matched_articles[1].is_primary
    assert [a.publisher for a in r.matched_articles] == ["jugantor.com", "jugantor.com", "prothomalo.com"]
    assert r.verification_mode == "VERIFIED_SOURCES"
