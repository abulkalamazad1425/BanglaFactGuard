from __future__ import annotations

import uuid
from datetime import date, datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import SubmissionStatus, SubmissionType, VerificationLabel
from app.features.submissions.models import Submission
from app.features.submissions.repository import SubmissionRepository
from app.features.verification.models import VerificationResultV2
from app.shared.dependencies import get_async_session

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

_VERIFIED_STATUSES = (SubmissionStatus.EXPERT_REVIEW, SubmissionStatus.FINALIZED)


class MethodDistribution(BaseModel):
    source_based: int
    multimodal: int
    photo_card: int


class PublicStatsResponse(BaseModel):
    total_submissions: int
    true_count: int
    false_count: int
    partially_true_count: int
    not_found_count: int
    pending_count: int
    method_distribution: MethodDistribution
    avg_verification_time_seconds: float | None


class TopSourceItem(BaseModel):
    source: str
    count: int


class ExplorerItem(BaseModel):
    submission_id: str
    headline: str | None
    submission_type: SubmissionType
    claimed_source_text: str | None
    final_label: VerificationLabel | None
    confidence: float | None
    published_date: date | None
    created_at: datetime


class ExplorerSearchResponse(BaseModel):
    items: list[ExplorerItem]
    total: int
    limit: int
    offset: int


@router.get(
    "/stats", response_model=PublicStatsResponse, summary="Public platform statistics"
)
async def get_public_stats(
    session: AsyncSession = Depends(get_async_session),
) -> PublicStatsResponse:

    total = (
        await session.execute(select(func.count()).select_from(Submission))
    ).scalar_one()

    pending = (
        await session.execute(
            select(func.count())
            .select_from(Submission)
            .where(Submission.status.in_((SubmissionStatus.PENDING, SubmissionStatus.PROCESSING)))
        )
    ).scalar_one()

    def _lc(lbl: VerificationLabel) -> int:
        return (
            select(func.count())
            .select_from(VerificationResultV2)
            .where(VerificationResultV2.final_label == lbl)
        )

    tc = (await session.execute(_lc(VerificationLabel.TRUE))).scalar_one()
    fc = (await session.execute(_lc(VerificationLabel.FALSE))).scalar_one()
    pc = (await session.execute(_lc(VerificationLabel.PARTIALLY_TRUE))).scalar_one()
    nc = (
        await session.execute(_lc(VerificationLabel.NOT_FOUND_IN_CLAIMED_SOURCE))
    ).scalar_one()

    def _mc(t: SubmissionType) -> int:
        return (
            select(func.count())
            .select_from(Submission)
            .where(Submission.submission_type == t)
        )

    source_based_c = (await session.execute(_mc(SubmissionType.SOURCE_BASED))).scalar_one()
    multimodal_c = (await session.execute(_mc(SubmissionType.MULTIMODAL))).scalar_one()
    photo_card_c = (await session.execute(_mc(SubmissionType.PHOTO_CARD))).scalar_one()

    avg_ms = (
        await session.execute(
            select(func.avg(VerificationResultV2.avg_verification_time_ms)).where(
                VerificationResultV2.avg_verification_time_ms.is_not(None)
            )
        )
    ).scalar_one()
    avg_seconds = round(avg_ms / 1000, 2) if avg_ms is not None else None

    return PublicStatsResponse(
        total_submissions=total,
        true_count=tc,
        false_count=fc,
        partially_true_count=pc,
        not_found_count=nc,
        pending_count=pending,
        method_distribution=MethodDistribution(
            source_based=source_based_c,
            multimodal=multimodal_c,
            photo_card=photo_card_c,
        ),
        avg_verification_time_seconds=avg_seconds,
    )


@router.get(
    "/top-sources",
    response_model=list[TopSourceItem],
    summary="Most frequently claimed sources",
)
async def get_top_sources(
    limit: int = Query(default=10, ge=1, le=50),
    session: AsyncSession = Depends(get_async_session),
) -> list[TopSourceItem]:
    stmt = (
        select(Submission.claimed_source_text, func.count().label("cnt"))
        .where(Submission.claimed_source_text.is_not(None))
        .group_by(Submission.claimed_source_text)
        .order_by(text("cnt DESC"))
        .limit(limit)
    )
    rows = (await session.execute(stmt)).all()
    return [TopSourceItem(source=row[0], count=row[1]) for row in rows]


@router.get(
    "/explorer",
    response_model=ExplorerSearchResponse,
    summary="Search and browse verified claims (Fact Explorer)",
    description=(
        "Browse and filter verified (in expert review or finalized) submissions "
        "by keyword, verdict, verification method, publication date range and "
        "news source. Each result links to the full report at "
        "GET /verify/{submission_id}."
    ),
)
async def search_explorer(
    keyword: str | None = Query(default=None, max_length=255),
    verdict: VerificationLabel | None = Query(default=None),
    method: SubmissionType | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    source_id: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_async_session),
) -> ExplorerSearchResponse:
    repo = SubmissionRepository(session)
    rows, total = await repo.search(
        keyword=keyword,
        verdict=verdict,
        method=method,
        date_from=date_from,
        date_to=date_to,
        source_id=source_id,
        limit=limit,
        offset=offset,
    )

    items = []
    for submission in rows:
        result_stmt = select(VerificationResultV2).where(
            VerificationResultV2.submission_id == submission.id
        )
        result = (await session.execute(result_stmt)).scalar_one_or_none()
        items.append(
            ExplorerItem(
                submission_id=str(submission.id),
                headline=submission.headline,
                submission_type=submission.submission_type,
                claimed_source_text=submission.claimed_source_text,
                final_label=result.final_label if result else None,
                confidence=result.confidence if result else None,
                published_date=submission.published_date,
                created_at=submission.created_at,
            )
        )

    return ExplorerSearchResponse(items=items, total=total, limit=limit, offset=offset)
