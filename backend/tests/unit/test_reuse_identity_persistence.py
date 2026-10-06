"""Claim identity, result reuse, cache freshness, durable persistence and
expert-snapshot preservation (acceptance 15-19, 29-31) against a real
(SQLite) database."""

from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import func, select, update

from app.core.constants import (
    VERIFICATION_PIPELINE_VERSION,
    ClaimScope,
    ContentStatus,
    DateStatus,
    OverallVerdict,
    SourceStatus,
    SubmissionStatus,
    SubmissionType,
)
from app.features.notifications.models import Notification
from app.features.sources.repository import SourceRepository
from app.features.submissions.models import Submission
from app.features.submissions.repository import (
    RetrievedArticleRepository,
    SubmissionRepository,
)
from app.features.verification.job_repository import VerificationJobRepository
from app.features.verification.models import VerificationJob, VerificationResult
from app.features.verification.pipeline.stages.s02_cache_lookup import CacheLookupStage
from app.features.verification.pipeline.stages.s13_result_persistence import ResultPersistenceStage
from app.features.verification.presenter import load_verification_response
from app.features.verification.repository import ResultRepository
from app.features.verification.reuse import result_is_reusable
from app.features.verification.schemas import VerificationRequest
from app.features.verification.service import VerificationService
from app.shared.utils.hashing import compute_claim_hash
from db_helpers import add_completed_submission, add_source, add_user, make_session_factory
from pipeline_helpers import FakeEmbedder, FakeNER, article, make_context, run_analysis

HEADLINE = "প্রধান উপদেষ্টা ঢাকায় নতুন সেতুর উদ্বোধন করেছেন"


@pytest.fixture
async def db():
    engine, factory = await make_session_factory()
    async with factory() as s:
        await add_source(s)
        await s.commit()
    yield factory
    await engine.dispose()


def _cache(pointer: dict | None = None) -> MagicMock:
    cache = MagicMock()
    cache.get_claim_result = AsyncMock(return_value=json.dumps(pointer).encode() if pointer else None)
    cache.set_claim_pointer = AsyncMock()
    cache.invalidate_claim = AsyncMock()
    return cache


def _service(session, cache=None) -> VerificationService:
    return VerificationService(
        submission_repo=SubmissionRepository(session),
        result_repo=ResultRepository(session),
        article_repo=RetrievedArticleRepository(session),
        source_repo=SourceRepository(session),
        cache_service=cache or _cache(),
        embedding_service=MagicMock(),
        ner_service=MagicMock(),
        nli_service=MagicMock(),
        http_client=MagicMock(),
    )


def _req(**kw) -> VerificationRequest:
    base = dict(headline=HEADLINE, claimed_source_text="প্রথম আলো")
    base.update(kw)
    return VerificationRequest(**base)


# ── 16: identity ─────────────────────────────────────────────────────────


def test_different_body_date_scope_source_or_version_are_distinct_identities():
    base = compute_claim_hash(HEADLINE, "prothomalo.com", ClaimScope.HEADLINE_WITH_BODY, body="বডি এক", published_date=date(2026, 1, 1))
    assert base != compute_claim_hash(HEADLINE, "prothomalo.com", ClaimScope.HEADLINE_WITH_BODY, body="বডি দুই", published_date=date(2026, 1, 1))
    assert base != compute_claim_hash(HEADLINE, "prothomalo.com", ClaimScope.HEADLINE_WITH_BODY, body="বডি এক", published_date=date(2026, 1, 2))
    assert base != compute_claim_hash(HEADLINE, "prothomalo.com", ClaimScope.HEADLINE_WITH_BODY, body="বডি এক")
    assert base != compute_claim_hash(HEADLINE, "jugantor.com", ClaimScope.HEADLINE_WITH_BODY, body="বডি এক", published_date=date(2026, 1, 1))
    assert base != compute_claim_hash(HEADLINE, "prothomalo.com", ClaimScope.HEADLINE_WITH_BODY, body="বডি এক", published_date=date(2026, 1, 1), version="v-old")


def test_identity_is_normalisation_stable_and_ignores_body_for_headline_only():
    a = compute_claim_hash("  প্রথম  আলো ​", "prothomalo.com", ClaimScope.HEADLINE_ONLY)
    assert a == compute_claim_hash("প্রথম আলো", "prothomalo.com", ClaimScope.HEADLINE_ONLY)
    assert a == compute_claim_hash("প্রথম আলো", "prothomalo.com", ClaimScope.HEADLINE_ONLY, body="ignored")
    # no ambiguous concatenation: moving text between fields changes the hash
    assert compute_claim_hash("ক|খ", "গ", ClaimScope.HEADLINE_ONLY) != compute_claim_hash("ক", "খ|গ", ClaimScope.HEADLINE_ONLY)


async def test_registration_hash_matches_s01_identity(db):
    async with db() as s:
        svc = _service(s)
        sid, status, cached = await svc.register_claim(_req(body_text="বডি টেক্সট", published_date=date(2026, 6, 7)))
        sub = await SubmissionRepository(s).get_by_id(sid)
        ctx = make_context(HEADLINE, body="বডি টেক্সট", published_date=date(2026, 6, 7))
        from app.shared.utils.hashing import compute_claim_hash as h

        assert sub.content_hash == h(ctx.normalized_headline, "prothomalo.com", ctx.claim_scope, body=ctx.normalized_body, published_date=ctx.published_date)


# ── registration: durable job, in-flight, distinct submissions ───────────


async def test_register_claim_commits_submission_and_job_together(db):
    async with db() as s:
        sid, status, cached = await _service(s).register_claim(_req())
    assert (status, cached) == (SubmissionStatus.PENDING, False)
    async with db() as s2:  # a fresh session sees committed rows
        sub = await SubmissionRepository(s2).get_by_id(sid)
        job = await VerificationJobRepository(s2).get_by_submission(sid)
        assert sub.processing_phase == "QUEUED" and sub.status == SubmissionStatus.PENDING
        assert job.status == "QUEUED" and job.kind == "SOURCE_BASED" and job.payload == {"force_refresh": False}


async def test_different_date_or_body_do_not_collapse_into_one_submission(db):
    async with db() as s:
        svc = _service(s)
        a, *_ = await svc.register_claim(_req(published_date=date(2026, 6, 7)))
        b, *_ = await svc.register_claim(_req(published_date=date(2026, 6, 8)))
        c, *_ = await svc.register_claim(_req(body_text="অন্য বডি"))
    assert len({a, b, c}) == 3


async def test_same_user_double_submit_returns_the_in_flight_submission(db):
    async with db() as s:
        user = await add_user(s)
        await s.commit()
        svc = _service(s)
        a, st_a, _ = await svc.register_claim(_req(), submitter_id=user.id)
        b, st_b, _ = await svc.register_claim(_req(), submitter_id=user.id)
        jobs = (await s.execute(select(func.count()).select_from(VerificationJob))).scalar_one()
    assert a == b and jobs == 1


# ── 19/8: reuse gives the requester THEIR OWN submission ─────────────────


async def test_reuse_copies_result_onto_requesters_own_submission(db):
    async with db() as s:
        owner = await add_user(s)
        other = await add_user(s)
        orig, orig_res = await add_completed_submission(s, headline=HEADLINE, submitter_id=owner.id)
        orig_res.analysis_details = {"timings": {"stage_ms": {"s04_source_search": 12345}}}
        await s.commit()
        sid, status, cached = await _service(s).register_claim(_req(), submitter_id=other.id)

        assert cached is True and sid != orig.id and status == SubmissionStatus.EXPERT_REVIEW
        mine = await SubmissionRepository(s).get_by_id(sid)
        assert mine.submitter_id == other.id and mine.duplicate_of_submission_id == orig.id
        res = await ResultRepository(s).get_by_submission_id(sid)
        assert res.reused_from_submission_id == orig.id
        assert "timings" not in res.analysis_details
        assert orig_res.analysis_details["timings"]["stage_ms"]["s04_source_search"] == 12345
        assert res.headline_similarity == orig_res.headline_similarity
        assert res.pipeline_version == VERIFICATION_PIPELINE_VERSION
        # original untouched, no job queued, requester notified once
        assert (await SubmissionRepository(s).get_by_id(orig.id)).submitter_id == owner.id
        assert (await s.execute(select(func.count()).select_from(VerificationJob))).scalar_one() == 0
        n = (await s.execute(select(func.count()).select_from(Notification).where(Notification.user_id == other.id))).scalar_one()
        assert n == 1


async def test_same_owner_reuse_returns_existing_submission(db):
    async with db() as s:
        owner = await add_user(s)
        orig, _ = await add_completed_submission(s, headline=HEADLINE, submitter_id=owner.id)
        await s.commit()
        sid, _, cached = await _service(s).register_claim(_req(), submitter_id=owner.id)
    assert cached is True and sid == orig.id


# ── 17: force_refresh bypasses every reuse path ──────────────────────────


async def test_force_refresh_bypasses_registration_reuse(db):
    async with db() as s:
        owner = await add_user(s)
        orig, _ = await add_completed_submission(s, headline=HEADLINE, submitter_id=owner.id)
        await s.commit()
        sid, status, cached = await _service(s).register_claim(_req(force_refresh=True), submitter_id=owner.id)
        job = await VerificationJobRepository(s).get_by_submission(sid)
    assert cached is False and sid != orig.id and status == SubmissionStatus.PENDING
    assert job.payload == {"force_refresh": True}


async def test_force_refresh_bypasses_s02_redis_and_database(db):
    async with db() as s:
        owner = await add_user(s)
        orig, _ = await add_completed_submission(s, headline=HEADLINE, submitter_id=owner.id)
        await s.commit()
        cache = _cache({"submission_id": str(orig.id), "pipeline_version": VERIFICATION_PIPELINE_VERSION})
        stage = CacheLookupStage(cache, SubmissionRepository(s), ResultRepository(s))

        ctx = make_context(HEADLINE)
        ctx.content_hash = orig.content_hash
        ctx.force_refresh = True
        assert (await stage.execute(ctx)).cache_hit is False
        cache.get_claim_result.assert_not_called()

        ctx = make_context(HEADLINE)
        ctx.content_hash = orig.content_hash
        out = await stage.execute(ctx)  # not forced -> redis pointer hit
        assert out.cache_hit and out.reused_from_submission_id == orig.id


# ── freshness / completeness / version ───────────────────────────────────


def _age(res, seconds: float):
    res.created_at = datetime.now(timezone.utc) - timedelta(seconds=seconds)


async def test_result_reusability_rules(db):
    async with db() as s:
        u = await add_user(s)
        _, ok = await add_completed_submission(s, headline="এক", submitter_id=u.id)
        assert result_is_reusable(ok)[0]

        _, old_version = await add_completed_submission(s, headline="দুই", submitter_id=u.id, pipeline_version=None)
        assert result_is_reusable(old_version) == (False, "pipeline_version_mismatch")

        _, inc_source = await add_completed_submission(s, headline="তিন", submitter_id=u.id, source_status=SourceStatus.INCOMPLETE)
        assert result_is_reusable(inc_source) == (False, "incomplete_check")
        _, no_verdict = await add_completed_submission(s, headline="চার", submitter_id=u.id, headline_check_status="UNDETERMINED")
        no_verdict.content_status = None
        assert result_is_reusable(no_verdict) == (False, "no_headline_verdict")
        _, body_missing = await add_completed_submission(
            s, headline="সাত", submitter_id=u.id, body="বডি", body_comparison_status="UNAVAILABLE"
        )
        assert result_is_reusable(body_missing) == (False, "body_scores_unavailable")
        _, inc_date = await add_completed_submission(s, headline="পাঁচ", submitter_id=u.id, date_status=DateStatus.INCOMPLETE)
        assert result_is_reusable(inc_date) == (False, "incomplete_check")

        # shorter freshness for NOT_FOUND
        _, nf = await add_completed_submission(s, headline="ছয়", submitter_id=u.id, source_status=SourceStatus.NOT_FOUND)
        _age(nf, 2 * 3600)  # 2h: past the NOT_FOUND window (1h) but inside the normal one (24h)
        assert result_is_reusable(nf) == (False, "stale")
        _age(ok, 2 * 3600)
        assert result_is_reusable(ok)[0]
        _age(ok, 3 * 86400)
        assert result_is_reusable(ok) == (False, "stale")

        # expert-finalized results are not subject to the automated window
        ok.overall_verdict = OverallVerdict.REAL
        assert result_is_reusable(ok) == (True, "finalized")


async def test_db_fallback_enforces_freshness_like_redis(db):
    async with db() as s:
        u = await add_user(s)
        sub, res = await add_completed_submission(s, headline=HEADLINE, submitter_id=u.id)
        _age(res, 3 * 86400)
        await s.commit()
        stage = CacheLookupStage(_cache(), SubmissionRepository(s), ResultRepository(s))
        ctx = make_context(HEADLINE)
        ctx.content_hash = sub.content_hash
        assert (await stage.execute(ctx)).cache_hit is False


async def test_stale_redis_pointer_is_rejected_and_invalidated(db):
    async with db() as s:
        u = await add_user(s)
        sub, res = await add_completed_submission(s, headline=HEADLINE, submitter_id=u.id, pipeline_version="v-old")
        await s.commit()
        cache = _cache({"submission_id": str(sub.id), "pipeline_version": VERIFICATION_PIPELINE_VERSION})
        ctx = make_context(HEADLINE)
        ctx.content_hash = "no-such-hash"
        out = await CacheLookupStage(cache, SubmissionRepository(s), ResultRepository(s)).execute(ctx)
    assert out.cache_hit is False
    cache.invalidate_claim.assert_awaited_once()


# ── 18: results are DB-authoritative; Redis never overlays ───────────────


async def test_result_is_identical_after_redis_expiry_and_ignores_stale_cache(db):
    analysis = {
        "pipeline_version": VERIFICATION_PIPELINE_VERSION,
        "headline_alteration": {
            "status": "COMPLETED", "verdict": "MATCHED", "reason": "exact", "exact_match": True,
            "claim_headline": HEADLINE, "source_title": HEADLINE,
        },
        "body_similarity": {"status": "COMPUTED", "jaccard": {"available": True, "value": 0.66}},
    }
    async with db() as s:
        u = await add_user(s)
        sub, res = await add_completed_submission(
            s, headline=HEADLINE, submitter_id=u.id, body="বডি", headline_similarity=0.77, analysis_details=analysis
        )
        await s.commit()
        stale = {"headline_check_status": "UNDETERMINED", "body_similarity": {"jaccard": 0.01}}
        with_cache = await _service(s, _cache(stale)).get_result(sub.id)
        no_cache = await _service(s, _cache(None)).get_result(sub.id)
    assert with_cache.model_dump() == no_cache.model_dump()
    assert no_cache.analysis.body_similarity.jaccard.value == 0.66
    assert no_cache.analysis.headline_alteration.exact_match is True
    assert no_cache.headline_check_status.value == "COMPLETED"
    assert no_cache.analysis is not None and no_cache.pipeline_version == VERIFICATION_PIPELINE_VERSION


async def test_legacy_content_verdict_is_never_relabelled_as_a_headline_verdict(db):
    """A row from the old pipeline (no headline_check_status, an old
    content-level verdict and an old-shaped analysis blob) still loads, but
    its content verdict is not shown as Headline Alteration."""
    legacy_analysis = {"pipeline_version": "v3.3", "headline_alteration": {"reason": "old", "kind": "none"},
                       "metrics": {}, "passages": [], "content_check": {"method": "x"}}
    async with db() as s:
        u = await add_user(s)
        sub, _ = await add_completed_submission(
            s, headline=HEADLINE, submitter_id=u.id, pipeline_version="v3.3", content_status=ContentStatus.ALTERED,
            headline_check_status=None, analysis_details=legacy_analysis,
        )
        await s.commit()
        r = await _service(s).get_result(sub.id)
    assert r.legacy_result is True
    assert r.ai_content_status is None and r.content_status is None and r.headline_check_status is None
    assert r.analysis is not None and r.analysis.headline_alteration is None


# ── 30: no automated overall verdict ─────────────────────────────────────


async def test_preliminary_result_has_no_overall_verdict(db):
    async with db() as s:
        u = await add_user(s)
        sub, _ = await add_completed_submission(s, headline=HEADLINE, submitter_id=u.id)
        await s.commit()
        r = await _service(s).get_result(sub.id)
    assert r.overall_verdict is None and r.is_finalized is False and r.review_pending is True


async def _persist(s, *, submission_id=None, headline=HEADLINE, ner=None):
    ctx = make_context(headline, top=article(headline, headline + "।"))
    ctx.content_hash = compute_claim_hash(headline, "prothomalo.com", ctx.claim_scope)
    ctx.submission_id = submission_id
    ctx = await run_analysis(ctx, ner=ner)
    stage = ResultPersistenceStage(
        SubmissionRepository(s), ResultRepository(s), RetrievedArticleRepository(s), _cache(), session=s
    )
    return await stage.execute(ctx)


async def test_s13_writes_the_result_columns_and_no_consensus_label(db):
    async with db() as s:
        out = await _persist(s)
        res = await ResultRepository(s).get_by_submission_id(out.submission_id)
    assert res.ai_consensus_label is None  # no automated truth vote
    assert res.overall_verdict is None
    assert res.headline_similarity is not None and res.headline_keyword_coverage == 1.0
    assert res.content_status == ContentStatus.MATCHED and res.headline_check_status == "COMPLETED"
    assert res.headline_exact_match is True and res.body_comparison_status == "SKIPPED"
    assert res.claim_scope == "HEADLINE_ONLY" and res.pipeline_version == VERIFICATION_PIPELINE_VERSION
    assert res.analysis_details["headline_alteration"]["source_title"] == HEADLINE
    assert res.analysis_details["body_similarity"]["status"] == "SKIPPED"


# ── 29: idempotent persistence, no duplicate results/notifications ───────


async def test_s13_is_idempotent_per_submission(db):
    async with db() as s:
        owner = await add_user(s)
        expert = await add_user(s, role="expert")
        sub = Submission(
            submission_type=SubmissionType.SOURCE_BASED, headline=HEADLINE, claimed_source_text="প্রথম আলো",
            submitter_id=owner.id, content_hash="x", status=SubmissionStatus.PENDING,
        )
        s.add(sub)
        await s.commit()

        first = await _persist(s, submission_id=sub.id)
        again = await _persist(s, submission_id=sub.id)  # retry / duplicate dispatch
        await s.commit()

        assert first.submission_id == again.submission_id == sub.id
        n_results = (await s.execute(select(func.count()).select_from(VerificationResult))).scalar_one()
        by_type = dict(
            (await s.execute(select(Notification.notification_type, func.count()).group_by(Notification.notification_type))).all()
        )
    assert n_results == 1
    assert by_type == {"VERIFICATION_COMPLETE": 1}


# ── 31: expert finalization / refresh never mutate the automated snapshot ─


async def test_expert_finalization_keeps_automated_snapshot_inspectable(db):
    async with db() as s:
        u = await add_user(s)
        sub, res = await add_completed_submission(s, headline=HEADLINE, submitter_id=u.id, content_status=ContentStatus.MATCHED)
        await ResultRepository(s).update(
            res,
            final_source_status=SourceStatus.CONFIRMED,
            final_content_status=ContentStatus.ALTERED,
            overall_verdict=OverallVerdict.MISLEADING,
            finalized_at=datetime.now(timezone.utc),
        )
        sub.status = SubmissionStatus.FINALIZED
        await s.commit()
        r = await _service(s).get_result(sub.id)
    assert r.overall_verdict == OverallVerdict.MISLEADING and r.is_finalized and not r.review_pending
    # The final decision is the overall verdict only; a legacy supplementary
    # final_content_status never replaces the preliminary AI finding.
    assert r.content_status == ContentStatus.MATCHED
    assert r.ai_content_status == ContentStatus.MATCHED  # automated snapshot preserved
    assert r.was_overridden is False and r.decided_by_admin is False


async def test_reverification_never_overwrites_a_reviewed_submission(db):
    async with db() as s:
        u = await add_user(s)
        sub, res = await add_completed_submission(s, headline=HEADLINE, submitter_id=u.id)
        await ResultRepository(s).update(res, overall_verdict=OverallVerdict.REAL, final_source_status=SourceStatus.CONFIRMED)
        sub.status = SubmissionStatus.FINALIZED
        await s.commit()
        snapshot = (res.headline_similarity, res.reasoning, res.created_at)

        # forced refresh of the same claim: same identity hash, NO submission id
        out = await _persist(s)
        assert out.submission_id != sub.id
        # and a run mistakenly pointed at the reviewed submission is a no-op
        same = await _persist(s, submission_id=sub.id)
        assert same.submission_id == sub.id
        await s.commit()
        after = await ResultRepository(s).get_by_submission_id(sub.id)
        assert (after.headline_similarity, after.reasoning, after.created_at) == snapshot
        assert after.overall_verdict == OverallVerdict.REAL
        assert (await SubmissionRepository(s).get_by_id(sub.id)).status == SubmissionStatus.FINALIZED
