"""Response snapshots of the main read endpoints over a fixed dataset.

Refactors of routers, presenters and queries must leave these JSON bodies
byte-for-byte identical. To regenerate on purpose (after a deliberate API
change): set BFG_UPDATE_SNAPSHOTS=1 and run this module once.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.core.constants import (
    ContentStatus,
    DateStatus,
    MultimodalPredictionLabel,
    OverallVerdict,
    SourceStatus,
    SubmissionStatus,
    SubmissionType,
)
from app.features.auth.models import User
from app.features.expert_review.models import ExpertProfile, ExpertReview, VotingConfig
from app.features.multimodal.models import MultimodalAnalysis
from app.features.submissions.models import PhotocardExtraction, RetrievedArticle, Submission
from app.features.notifications.models import Notification
from app.features.verification.models import VerificationResult
from tests.unit.db_helpers import make_session_factory

SNAPSHOT = Path(__file__).parent / "snapshots" / "api_responses.json"
T0 = datetime(2026, 1, 10, 6, 0, tzinfo=timezone.utc)


def _id(n: int) -> uuid.UUID:
    # Contains letters: SQLite's numeric affinity would turn an all-digit
    # hex string (e.g. UUID(int=1)) back into an integer.
    return uuid.UUID(f"{n:08d}-aaaa-4aaa-8aaa-aaaaaaaaaaaa")


def _ts(minutes: int) -> datetime:
    return T0.replace(minute=minutes % 60, hour=6 + minutes // 60)


OWNER, OTHER, EXPERT, ADMIN = _id(1), _id(2), _id(3), _id(4)
S_CONFIRMED, S_NOT_FOUND, S_COPY, S_FINAL, S_ESCALATED = _id(11), _id(12), _id(13), _id(14), _id(15)
S_MULTI, S_CARD, S_PENDING, S_FAILED = _id(16), _id(17), _id(18), _id(19)

ANALYSIS = {
    "pipeline_version": "v4.0-headline-title-body-scores",
    "claim_scope": "HEADLINE_ONLY",
    "metrics": {
        "headline_title_similarity": {"state": "COMPUTED", "value": 0.97},
        "title_keyword_coverage": {"state": "COMPUTED", "value": 1.0},
    },
    "source_basis": ["headline/title similarity 0.97 ≥ 0.85"],
    "headline_alteration": {
        "status": "COMPLETED",
        "verdict": "MATCHED",
        "reason": "The claim headline exactly matches the source title.",
        "exact_match": True,
        "basis": "exact",
        "claim_headline": "ঢাকায় নতুন মেট্রোরেল চালু",
        "source_title": "ঢাকায় নতুন মেট্রোরেল চালু",
        "source_publisher": "prothomalo.com",
        "source_url": "https://www.prothomalo.com/bangladesh/a1",
        "method": "headline-title-v1",
    },
    "body_similarity": {"status": "SKIPPED", "reason": "The claim has no body."},
}


class _Storage:
    async def get_presigned_url(self, key):
        return f"https://img.test/{key}"


async def _seed(session) -> None:
    def user(uid, role, name):
        return User(
            id=uid, email=f"{role}{uid.hex[:8]}@example.com", hashed_password="x", full_name=name,
            role=role, is_active=True, total_submissions=0, created_at=T0, updated_at=T0,
        )

    session.add_all([
        user(OWNER, "user", "Owner"), user(OTHER, "user", "Other"),
        user(EXPERT, "expert", "Expert One"), user(ADMIN, "admin", "Admin"),
    ])
    session.add(VotingConfig(
        id=_id(90), min_expert_votes=3, activation_threshold_votes=10, verified_threshold=5.0,
        lead_margin=1.0, max_review_votes=None, max_review_hours=None, created_at=T0, updated_at=T0,
    ))
    session.add(ExpertProfile(
        id=_id(91), user_id=EXPERT, area_of_expertise="General", credibility_score=None,
        total_votes=1, correct_votes=1, completed_reviews_count=1, is_active=True,
        created_at=T0, updated_at=T0,
    ))

    def sub(sid, minute, *, type_=SubmissionType.SOURCE_BASED, status=SubmissionStatus.EXPERT_REVIEW,
            submitter=OWNER, headline="ঢাকায় নতুন মেট্রোরেল চালু", **kw):
        return Submission(
            id=sid, submission_type=type_, headline=headline, claimed_source_text="prothomalo.com",
            submitter_id=submitter, content_hash=f"hash-{sid.hex[:8]}", status=status,
            processing_phase=kw.pop("phase", "DONE"), created_at=_ts(minute), updated_at=_ts(minute), **kw,
        )

    session.add_all([
        sub(S_CONFIRMED, 1, published_date=date(2026, 1, 9)),
        sub(S_NOT_FOUND, 2, headline="অজানা খবর যা পাওয়া যায়নি"),
        sub(S_COPY, 3, submitter=OTHER, duplicate_of_submission_id=S_FINAL),
        sub(S_FINAL, 4, status=SubmissionStatus.FINALIZED, submitter=OTHER, headline="চূড়ান্ত দাবি"),
        sub(S_ESCALATED, 5, status=SubmissionStatus.ESCALATED, submitter=OTHER, headline="জটিল দাবি",
            escalated_at=_ts(30)),
        sub(S_MULTI, 6, type_=SubmissionType.MULTIMODAL, body_text="ছবি সহ খবরের বিস্তারিত বিবরণ", headline="ছবির খবর"),
        sub(S_CARD, 7, type_=SubmissionType.PHOTO_CARD, headline="ফটোকার্ডের শিরোনাম"),
        sub(S_PENDING, 8, status=SubmissionStatus.PENDING, phase="QUEUED", headline=None),
        sub(S_FAILED, 9, status=SubmissionStatus.FAILED, phase="FAILED", failure_reason="Could not read."),
    ])
    await session.flush()

    session.add(RetrievedArticle(
        id=_id(50), submission_id=S_CONFIRMED, url="https://www.prothomalo.com/bangladesh/a1",
        url_hash="u1", title="ঢাকায় নতুন মেট্রোরেল চালু", body="বিস্তারিত " * 60,
        published_date=date(2026, 1, 9), rank_score=0.95, extraction_success=True, retrieved_at=T0,
    ))
    await session.flush()

    def result(rid, sid, minute, source, **kw):
        confirmed = source == SourceStatus.CONFIRMED
        return VerificationResult(
            id=rid, submission_id=sid, source_status=source,
            content_status=kw.pop("content", ContentStatus.MATCHED if confirmed else None),
            headline_check_status=kw.pop("check", "COMPLETED" if confirmed else "SOURCE_NOT_FOUND"),
            headline_exact_match=kw.pop("exact", True if confirmed else None),
            body_comparison_status="SKIPPED", date_status=kw.pop("date", None),
            confidence=0.9 if confirmed else 1.0, reasoning=f"reasoning {sid.hex[:8]}",
            avg_verification_time_ms=1234, claim_scope="HEADLINE_ONLY",
            pipeline_version="v4.0-headline-title-body-scores",
            analysis_details=ANALYSIS if confirmed else {"pipeline_version": "v4.0-headline-title-body-scores"},
            created_at=_ts(minute), updated_at=_ts(minute), **kw,
        )

    session.add_all([
        result(_id(61), S_CONFIRMED, 1, SourceStatus.CONFIRMED, top_article_id=_id(50), date=DateStatus.MATCHED),
        result(_id(62), S_NOT_FOUND, 2, SourceStatus.NOT_FOUND),
        result(_id(64), S_FINAL, 4, SourceStatus.CONFIRMED, overall_verdict=OverallVerdict.REAL, finalized_at=_ts(40)),
        result(_id(63), S_COPY, 3, SourceStatus.CONFIRMED, reused_from_submission_id=S_FINAL),
        result(_id(65), S_ESCALATED, 5, SourceStatus.CONFIRMED, content=ContentStatus.ALTERED, exact=False),
        result(_id(67), S_CARD, 7, SourceStatus.CONFIRMED),
    ])
    session.add(MultimodalAnalysis(
        id=_id(70), submission_id=S_MULTI, image_object_key="multimodal/16/x.png",
        prediction=MultimodalPredictionLabel.FAKE, confidence_fake=0.8, confidence_real=0.2,
        model_version="test", created_at=_ts(6), updated_at=_ts(6),
    ))
    session.add(PhotocardExtraction(
        id=_id(71), submission_id=S_CARD, image_object_key="photocard/17/card.png", status="SUCCEEDED",
        model_version="gemini-test", attempts=1, extraction_details={"attempts": []},
        created_at=_ts(7), updated_at=_ts(7),
    ))
    session.add(ExpertReview(
        id=_id(80), submission_id=S_FINAL, reviewer_id=EXPERT, ai_source_status=SourceStatus.CONFIRMED,
        ai_content_status=ContentStatus.MATCHED, vote_overall_verdict=OverallVerdict.REAL,
        justification="Matches the outlet's own report word for word, so the claim is real.",
        credibility_weight=1.0, status="finalized", is_admin_decision=False,
        created_at=_ts(35), updated_at=_ts(35),
    ))

    def note(nid, user, minute, read, kind="VERIFICATION_COMPLETE"):
        return Notification(
            id=_id(nid), user_id=user, title=f"title {nid}", body=f"body {nid}", notification_type=kind,
            link_url=f"/verify/{nid}", is_read=read, created_at=_ts(minute), updated_at=_ts(minute),
        )

    session.add_all([
        note(100, OWNER, 20, False), note(101, OWNER, 21, True),
        note(102, OWNER, 22, False, "EXPERT_REVIEW_COMPLETE"), note(103, OTHER, 23, False),
    ])
    await session.commit()


REQUESTS = [
    ("explorer", "/api/v1/dashboard/explorer", None),
    ("explorer_review", "/api/v1/dashboard/explorer?review_state=review", None),
    ("explorer_card", "/api/v1/dashboard/explorer?method=PHOTO_CARD", None),
    ("public_stats", "/api/v1/dashboard/stats", None),
    ("top_sources", "/api/v1/dashboard/top-sources", None),
    ("my_submissions", "/api/v1/users/me/submissions", OWNER),
    ("my_submissions_other", "/api/v1/users/me/submissions", OTHER),
    ("my_stats", "/api/v1/users/me/submissions/stats", OWNER),
    ("my_profile", "/api/v1/users/me/profile", OWNER),
    ("verify_confirmed", f"/api/v1/verify/{S_CONFIRMED}", None),
    ("verify_not_found", f"/api/v1/verify/{S_NOT_FOUND}", None),
    ("verify_copy", f"/api/v1/verify/{S_COPY}", None),
    ("verify_final", f"/api/v1/verify/{S_FINAL}", None),
    ("verify_pending_anonymous", f"/api/v1/verify/{S_PENDING}", None),
    ("verify_status_failed_owner", f"/api/v1/verify/{S_FAILED}/status", OWNER),
    ("photocard", f"/api/v1/photocard/{S_CARD}", None),
    ("multimodal_by_submission", f"/api/v1/multimodal/by-submission/{S_MULTI}", None),
    ("submission_lookup_copy", f"/api/v1/submissions/{S_COPY}", None),
    ("submission_lookup_pending_owner", f"/api/v1/submissions/{S_PENDING}", OWNER),
    ("submission_lookup_pending_other", f"/api/v1/submissions/{S_PENDING}", OTHER),
    ("voting_details_final", f"/api/v1/submissions/{S_FINAL}/voting-details", None),
    ("voting_details_open", f"/api/v1/submissions/{S_CONFIRMED}/voting-details", None),
    ("expert_queue", "/api/v1/expert/queue", EXPERT),
    ("expert_queue_item", f"/api/v1/expert/queue/{S_CONFIRMED}", EXPERT),
    ("expert_queue_escalated_forbidden", f"/api/v1/expert/queue/{S_ESCALATED}", EXPERT),
    ("expert_history", "/api/v1/expert/history", EXPERT),
    ("expert_stats", "/api/v1/expert/stats", EXPERT),
    ("expert_credibility", "/api/v1/expert/credibility", EXPERT),
    ("admin_queue", "/api/v1/expert/queue", ADMIN),
    ("admin_stats", "/api/v1/admin/stats", ADMIN),
    ("admin_dashboard", "/api/v1/admin/dashboard", ADMIN),
    ("admin_experts", "/api/v1/admin/experts", ADMIN),
    ("admin_voting_config", "/api/v1/admin/voting-config", ADMIN),
    ("notifications", "/api/v1/notifications", OWNER),
    ("notifications_count", "/api/v1/notifications/count", OWNER),
    ("notifications_unread", "/api/v1/notifications?unread_only=true", OWNER),
    ("notifications_page", "/api/v1/notifications?limit=1&offset=1", OWNER),
    ("notifications_other", "/api/v1/notifications", OTHER),
    ("notifications_anonymous", "/api/v1/notifications", None),
    ("mark_read_others_notification", ("POST", f"/api/v1/notifications/{_id(103)}/read"), OWNER),
    ("notifications_other_after_foreign_mark", "/api/v1/notifications/count", OTHER),
    ("mark_read_own", ("POST", f"/api/v1/notifications/{_id(100)}/read"), OWNER),
    ("notifications_count_after_mark", "/api/v1/notifications/count", OWNER),
    ("mark_all_read", ("POST", "/api/v1/notifications/read-all"), OWNER),
    ("notifications_after_read_all", "/api/v1/notifications", OWNER),
    ("notifications_other_after_owner_read_all", "/api/v1/notifications/count", OTHER),
    ("profile_update_expert_forbidden", ("PUT", "/api/v1/users/me/profile", {"full_name": "X"}), EXPERT),
    ("profile_update_empty", ("PUT", "/api/v1/users/me/profile", {}), OWNER),
    ("profile_update_name", ("PUT", "/api/v1/users/me/profile", {"full_name": "Owner Renamed"}), OWNER),
    ("profile_after_update", "/api/v1/users/me/profile", OWNER),
    ("expert_profile_unchanged", "/api/v1/users/me/profile", EXPERT),
]

_VOLATILE_KEYS = {"request_id"}


def _normalise(value):
    if isinstance(value, dict):
        return {k: ("<volatile>" if k in _VOLATILE_KEYS else _normalise(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [_normalise(v) for v in value]
    return value


async def _collect() -> dict:
    from app.db import engine as db_engine
    from app.features.auth.security import get_current_user, get_current_user_optional
    from app.main import create_app
    from app.shared import dependencies

    engine, factory = await make_session_factory()
    async with engine.begin() as conn:
        await conn.run_sync(
            lambda c: [t.__table__.create(c) for t in (VotingConfig, ExpertProfile, MultimodalAnalysis)]
        )
    async with factory() as session:
        await _seed(session)

    viewer = SimpleNamespace(current=None)

    async def session_dep():
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def current_user():
        if viewer.current is None:
            from app.core.exceptions import TokenInvalidError

            raise TokenInvalidError()
        async with factory() as session:
            return await session.get(User, viewer.current)

    async def optional_user():
        if viewer.current is None:
            return None
        async with factory() as session:
            return await session.get(User, viewer.current)

    with patch("app.main.lifespan"):
        app = create_app()
    app.dependency_overrides[dependencies.get_async_session] = session_dep
    app.dependency_overrides[db_engine.get_async_session] = session_dep
    app.dependency_overrides[get_current_user] = current_user
    app.dependency_overrides[get_current_user_optional] = optional_user
    loader = MagicMock(is_loaded=True)
    for name in ("cache_service", "embedding_service", "ner_service", "nli_service", "http_client"):
        setattr(app.state, name, MagicMock())
    app.state.photocard_storage = _Storage()
    app.state.multimodal_storage = _Storage()
    app.state.multimodal_loader = loader

    out: dict = {}
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            for name, url, who in REQUESTS:
                viewer.current = who
                method, path, payload = (url + (None,))[:3] if isinstance(url, tuple) else ("GET", url, None)
                response = await client.request(method, path, json=payload)
                body = response.json() if response.content else None
                out[name] = {"status": response.status_code, "body": _normalise(body)}
    finally:
        await engine.dispose()
    return out


@pytest.mark.asyncio
async def test_read_endpoints_match_snapshot():
    actual = await _collect()
    if os.environ.get("BFG_UPDATE_SNAPSHOTS") == "1" or not SNAPSHOT.exists():
        SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
        SNAPSHOT.write_text(json.dumps(actual, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        pytest.skip("snapshot written; re-run to compare")
    expected = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    assert set(actual) == set(expected)
    for name in expected:
        assert actual[name] == expected[name], f"response changed: {name}"
