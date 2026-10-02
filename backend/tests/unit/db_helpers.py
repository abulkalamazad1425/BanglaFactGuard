"""A real (SQLite, in-memory) database for the tables the verification flow
touches. The shared integration fixtures cannot build the full metadata on
SQLite (pgvector/ARRAY columns elsewhere), so only the needed tables are
created, with JSONB rendered as JSON.
"""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.pool import StaticPool


@compiles(JSONB, "sqlite")
def _jsonb_sqlite(type_, compiler, **kw):  # pragma: no cover - trivial shim
    return "JSON"


from app.core.constants import ClaimScope, SourceStatus, SubmissionStatus, SubmissionType  # noqa: E402
from app.features.auth.models import User  # noqa: E402
from app.features.sources.models import VerifiedSource  # noqa: E402
from app.features.submissions.models import Submission  # noqa: E402
from app.features.verification.models import VerificationResultV2  # noqa: E402
from app.shared.models_registry import Base  # noqa: E402
from app.shared.utils.hashing import compute_claim_hash  # noqa: E402
from app.core.constants import VERIFICATION_PIPELINE_VERSION  # noqa: E402

TABLES = [
    "users", "verified_sources", "submissions", "ocr_extractions", "retrieved_articles_v2",
    "verification_results_v2", "verification_jobs", "notifications", "source_evidence_queries",
    "verification_logs",
]


async def make_session_factory(path: str | None = None):
    """File-backed when `path` is given (needed when a background worker and
    the test use different sessions at once: each session gets its own
    connection, as in production). In-memory otherwise."""
    if path:
        engine = create_async_engine(
            f"sqlite+aiosqlite:///{path}", connect_args={"timeout": 30}
        )
    else:
        engine = create_async_engine(
            "sqlite+aiosqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    tables = [Base.metadata.tables[n] for n in TABLES]
    async with engine.begin() as conn:
        if path:
            await conn.exec_driver_sql("PRAGMA journal_mode=WAL")
        await conn.run_sync(lambda c: Base.metadata.create_all(c, tables=tables))
    return engine, async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def add_user(session: AsyncSession, *, role: str = "user") -> User:
    user = User(
        id=uuid.uuid4(),
        email=f"{uuid.uuid4().hex[:8]}@example.com",
        hashed_password="x",
        role=role,
        is_active=True,
    )
    session.add(user)
    await session.flush()
    return user


async def add_source(session: AsyncSession, canonical: str = "prothomalo.com") -> VerifiedSource:
    src = VerifiedSource(
        id=uuid.uuid4(),
        canonical_name=canonical,
        display_name="প্রথম আলো",
        base_url=f"https://www.{canonical}",
        aliases=["প্রথম আলো"],
        language="bn",
        search_language="bn",
        js_rendered=False,
        is_active=True,
    )
    session.add(src)
    await session.flush()
    return src


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
) -> tuple[Submission, VerificationResultV2]:
    from app.core.constants import ContentStatus

    scope = ClaimScope.HEADLINE_WITH_BODY if body else ClaimScope.HEADLINE_ONLY
    sub = Submission(
        id=uuid.uuid4(),
        submission_type=submission_type,
        headline=headline,
        body_text=body,
        claimed_source_text="প্রথম আলো",
        published_date=published,
        submitter_id=submitter_id,
        content_hash=compute_claim_hash(
            headline, "prothomalo.com", scope, body=body, published_date=published
        ),
        status=SubmissionStatus.EXPERT_REVIEW,
        processing_phase="DONE",
    )
    session.add(sub)
    await session.flush()
    res = VerificationResultV2(
        id=uuid.uuid4(),
        submission_id=sub.id,
        source_status=source_status,
        content_status=content_status
        if content_status is not None
        else (ContentStatus.MATCHED if source_status == SourceStatus.CONFIRMED else None),
        date_status=date_status,
        confidence=0.9,
        reasoning="r",
        semantic_similarity=result_fields.pop("semantic_similarity", 0.91),
        headline_similarity=result_fields.pop("headline_similarity", 0.91),
        body_similarity=result_fields.pop("body_similarity", None),
        passage_similarity=0.8,
        headline_keyword_coverage=1.0,
        keyword_overlap=1.0,
        claim_scope=scope.value,
        pipeline_version=pipeline_version,
        manipulation_flags={"check_states": {"numbers": "PASSED"}, "discrepancies": []},
        analysis_details={"pipeline_version": pipeline_version, "metrics": {}, "passages": []},
        **result_fields,
    )
    session.add(res)
    await session.flush()
    return sub, res
