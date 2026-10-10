"""A real SQLite database for service/repository unit tests, plus row builders.

Every table is created (Postgres-only types are rendered as JSON by the
shims in tests/conftest.py). SQLite does not enforce FK cascades/SET NULL:
tests that depend on them emulate them explicitly.
"""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import JSON
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.constants import (
    VERIFICATION_PIPELINE_VERSION,
    ClaimScope,
    ContentStatus,
    MultimodalPredictionLabel,
    SourceStatus,
    SubmissionStatus,
    SubmissionType,
)
from app.features.auth.models import User
from app.features.expert_review.models import VotingConfig
from app.features.multimodal.models import MultimodalAnalysis
from app.features.sources.models import VerifiedSource
from app.features.submissions.models import Submission
from app.features.verification.models import VerificationResult
from app.shared.models_registry import Base
from app.shared.utils.hashing import compute_claim_hash


async def make_session_factory(path: str | None = None):
    """File-backed when `path` is given (needed when a background worker and
    the test use different sessions at once: each session gets its own
    connection, as in production). In-memory otherwise."""
    if path:
        engine = create_async_engine(f"sqlite+aiosqlite:///{path}", connect_args={"timeout": 30})
    else:
        engine = create_async_engine(
            "sqlite+aiosqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    async with engine.begin() as conn:
        if path:
            await conn.exec_driver_sql("PRAGMA journal_mode=WAL")
        await conn.run_sync(Base.metadata.create_all)
    return engine, async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


def store_vectors_as_json(monkeypatch) -> None:
    """Let the multimodal embedding columns (Postgres ARRAY) hold lists on SQLite."""
    for name in ("text_embedding", "image_embedding", "combined_embedding"):
        monkeypatch.setattr(MultimodalAnalysis.__table__.c[name], "type", JSON())


async def add_user(session: AsyncSession, *, role: str = "user", **fields) -> User:
    values = dict(email=f"{uuid.uuid4().hex[:8]}@example.com", hashed_password="x", is_active=True)
    values.update(fields)
    user = User(id=uuid.uuid4(), role=role, **values)
    session.add(user)
    await session.flush()
    return user


async def add_source(session: AsyncSession, canonical: str = "prothomalo.com", **fields) -> VerifiedSource:
    values = dict(
        display_name="প্রথম আলো",
        base_url=f"https://www.{canonical}",
        aliases=["প্রথম আলো"],
        language="bn",
        search_language="bn",
        js_rendered=False,
        is_active=True,
    )
    values.update(fields)
    src = VerifiedSource(id=uuid.uuid4(), canonical_name=canonical, **values)
    session.add(src)
    await session.flush()
    return src


async def add_voting_config(session: AsyncSession, **fields) -> VotingConfig:
    values = dict(
        min_expert_votes=2, activation_threshold_votes=10, verified_threshold=2.0, lead_margin=1.0,
        max_review_votes=None, max_review_hours=None,
    )
    values.update(fields)
    config = VotingConfig(**values)
    session.add(config)
    await session.flush()
    return config


async def add_completed_submission(
    session: AsyncSession,
    *,
    headline: str,
    submitter_id: uuid.UUID | None,
    source_status: SourceStatus = SourceStatus.CONFIRMED,
    body: str | None = None,
    published: date | None = None,
    submission_type: SubmissionType = SubmissionType.SOURCE_BASED,
    pipeline_version: str | None = VERIFICATION_PIPELINE_VERSION,
    content_status=None,
    date_status=None,
    **result_fields,
) -> tuple[Submission, VerificationResult]:
    """A submission whose automated check is done (EXPERT_REVIEW) with its result."""
    scope = ClaimScope.HEADLINE_WITH_BODY if body else ClaimScope.HEADLINE_ONLY
    sub = Submission(
        id=uuid.uuid4(),
        submission_type=submission_type,
        headline=headline,
        body_text=body,
        claimed_source_text="প্রথম আলো",
        published_date=published,
        submitter_id=submitter_id,
        content_hash=compute_claim_hash(headline, "prothomalo.com", scope, body=body, published_date=published),
        status=SubmissionStatus.EXPERT_REVIEW,
        processing_phase="DONE",
    )
    session.add(sub)
    await session.flush()
    confirmed = source_status == SourceStatus.CONFIRMED
    verdict = content_status if content_status is not None else (ContentStatus.MATCHED if confirmed else None)
    headline_status = result_fields.pop(
        "headline_check_status",
        "COMPLETED" if verdict is not None
        else "SOURCE_NOT_FOUND" if source_status == SourceStatus.NOT_FOUND
        else "SOURCE_CHECK_INCOMPLETE" if source_status == SourceStatus.INCOMPLETE
        else "UNDETERMINED",
    )
    res = VerificationResult(
        id=uuid.uuid4(),
        submission_id=sub.id,
        source_status=source_status,
        content_status=verdict,
        headline_check_status=headline_status,
        headline_exact_match=result_fields.pop("headline_exact_match", False if verdict else None),
        body_comparison_status=result_fields.pop("body_comparison_status", "COMPUTED" if body else "SKIPPED"),
        date_status=date_status,
        confidence=0.9,
        reasoning="r",
        headline_similarity=result_fields.pop("headline_similarity", 0.91),
        headline_keyword_coverage=1.0,
        passage_keyword_coverage=1.0,
        claim_scope=scope.value,
        pipeline_version=pipeline_version,
        analysis_details=result_fields.pop("analysis_details", {"pipeline_version": pipeline_version, "metrics": {}}),
        **result_fields,
    )
    session.add(res)
    await session.flush()
    return sub, res


async def add_multimodal_submission(
    session: AsyncSession,
    *,
    headline: str = "ছবির খবর",
    submitter_id: uuid.UUID | None = None,
    prediction: MultimodalPredictionLabel = MultimodalPredictionLabel.FAKE,
    **analysis_fields,
) -> tuple[Submission, MultimodalAnalysis]:
    """A text-and-image submission with its stored AI prediction."""
    sub = Submission(
        id=uuid.uuid4(),
        submission_type=SubmissionType.MULTIMODAL,
        headline=headline,
        body_text="ছবি সহ খবরের বিস্তারিত বিবরণ",
        submitter_id=submitter_id,
        content_hash=uuid.uuid4().hex,
        status=SubmissionStatus.EXPERT_REVIEW,
        processing_phase="DONE",
    )
    session.add(sub)
    await session.flush()
    fake = prediction == MultimodalPredictionLabel.FAKE
    analysis = MultimodalAnalysis(
        id=uuid.uuid4(),
        submission_id=sub.id,
        image_object_key=f"multimodal/{sub.id}/image.png",
        prediction=prediction,
        confidence_fake=0.8 if fake else 0.2,
        confidence_real=0.2 if fake else 0.8,
        model_version="test",
        **analysis_fields,
    )
    session.add(analysis)
    await session.flush()
    return sub, analysis
