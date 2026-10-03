from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import (
    ContentStatus,
    DateStatus,
    MultimodalPredictionLabel,
    OverallVerdict,
    SourceStatus,
    SubmissionStatus,
    SubmissionType,
)
from app.features.expert_review.overall_verdict import derive_ai_overall_verdict_multimodal
from app.features.multimodal.models import MultimodalAnalysis
from app.features.multimodal.storage_service import MultimodalStorageService
from app.features.photocard.storage_service import PhotoCardStorageService
from app.features.submissions.models import OcrExtraction, Submission
from app.features.submissions.repository import SubmissionRepository
from app.features.verification.models import VerificationResult
from app.shared.dependencies import get_async_session

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

_VERIFIED_STATUSES = (SubmissionStatus.EXPERT_REVIEW, SubmissionStatus.FINALIZED)


class MethodDistribution(BaseModel):
    source_based: int
    multimodal: int
    photo_card: int


class PublicStatsResponse(BaseModel):
    total_submissions: int
    source_confirmed_count: int
    source_not_found_count: int
    content_matched_count: int
    content_altered_count: int
    date_matched_count: int
    date_mismatched_count: int
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
    overall_verdict: OverallVerdict | None = Field(
        default=None,
        description=(
            "The expert-finalized Overall verdict. NULL until expert review "
            "finalizes the claim - the automated system never sets it."
        ),
    )
    is_finalized: bool = Field(
        default=False,
        description="True once expert review has finalized overall_verdict.",
    )
    source_status: SourceStatus | None = None
    content_status: ContentStatus | None = None
    date_status: DateStatus | None = None
    confidence: float | None
    image_url: str | None = Field(
        default=None, description="Thumbnail for MULTIMODAL/PHOTO_CARD submissions"
    )
    published_date: date | None
    created_at: datetime


class ExplorerSearchResponse(BaseModel):
    items: list[ExplorerItem]
    total: int
    limit: int
    offset: int
    archive_summary: dict[str, int] = Field(default_factory=dict)


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

    def _sc(status: SourceStatus) -> int:
        return (
            select(func.count())
            .select_from(VerificationResult)
            .where(VerificationResult.source_status == status)
        )

    def _cc(status: ContentStatus) -> int:
        return (
            select(func.count())
            .select_from(VerificationResult)
            .where(VerificationResult.content_status == status)
        )

    def _dc(status: DateStatus) -> int:
        return (
            select(func.count())
            .select_from(VerificationResult)
            .where(VerificationResult.date_status == status)
        )

    source_confirmed = (
        await session.execute(_sc(SourceStatus.CONFIRMED))
    ).scalar_one()
    source_not_found = (
        await session.execute(_sc(SourceStatus.NOT_FOUND))
    ).scalar_one()
    content_matched = (
        await session.execute(_cc(ContentStatus.MATCHED))
    ).scalar_one()
    content_altered = (
        await session.execute(_cc(ContentStatus.ALTERED))
    ).scalar_one()
    date_matched = (await session.execute(_dc(DateStatus.MATCHED))).scalar_one()
    date_mismatched = (
        await session.execute(_dc(DateStatus.MISMATCHED))
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
            select(func.avg(VerificationResult.avg_verification_time_ms)).where(
                VerificationResult.avg_verification_time_ms.is_not(None)
            )
        )
    ).scalar_one()
    avg_seconds = round(avg_ms / 1000, 2) if avg_ms is not None else None

    return PublicStatsResponse(
        total_submissions=total,
        source_confirmed_count=source_confirmed,
        source_not_found_count=source_not_found,
        content_matched_count=content_matched,
        content_altered_count=content_altered,
        date_matched_count=date_matched,
        date_mismatched_count=date_mismatched,
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
    request: Request,
    keyword: str | None = Query(default=None, max_length=255),
    source_status: SourceStatus | None = Query(default=None),
    content_status: ContentStatus | None = Query(default=None),
    date_status: DateStatus | None = Query(default=None),
    overall_verdict: OverallVerdict | None = Query(
        default=None,
        description=(
            "Matches only expert-finalized claims — spans every submission "
            "type, unlike source/content/date_status which only apply to "
            "SOURCE_BASED/PHOTO_CARD."
        ),
    ),
    method: SubmissionType | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    source_id: uuid.UUID | None = Query(default=None),
    review_state: Literal['finalized', 'review'] | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_async_session),
) -> ExplorerSearchResponse:
    repo = SubmissionRepository(session)
    rows, total = await repo.search(
        keyword=keyword,
        source_status=source_status,
        content_status=content_status,
        date_status=date_status,
        overall_verdict=overall_verdict,
        method=method,
        date_from=date_from,
        date_to=date_to,
        source_id=source_id,
        review_state=review_state,
        limit=limit,
        offset=offset,
    )

    multimodal_storage: MultimodalStorageService | None = getattr(
        request.app.state, "multimodal_storage", None
    )
    photocard_storage: PhotoCardStorageService | None = getattr(
        request.app.state, "photocard_storage", None
    )

    items = []
    for submission in rows:
        if submission.submission_type == SubmissionType.MULTIMODAL:
            mm_stmt = select(MultimodalAnalysis).where(
                MultimodalAnalysis.submission_id == submission.id
            )
            mm = (await session.execute(mm_stmt)).scalar_one_or_none()

            image_url = (
                await multimodal_storage.get_presigned_url(mm.image_object_key)
                if mm and multimodal_storage
                else None
            )
            overall = (
                mm.expert_overall_verdict
                or derive_ai_overall_verdict_multimodal(mm.prediction)
                if mm
                else None
            )
            items.append(
                ExplorerItem(
                    submission_id=str(submission.id),
                    headline=submission.headline,
                    submission_type=submission.submission_type,
                    claimed_source_text=None,
                    overall_verdict=overall,
                    is_finalized=bool(mm and mm.expert_overall_verdict),
                    confidence=(
                        (
                            mm.confidence_fake
                            if mm.prediction == MultimodalPredictionLabel.FAKE
                            else mm.confidence_real
                        )
                        if mm
                        else None
                    ),
                    image_url=image_url,
                    published_date=submission.published_date,
                    created_at=submission.created_at,
                )
            )
            continue

        result_stmt = select(VerificationResult).where(
            VerificationResult.submission_id == submission.id
        )
        result = (await session.execute(result_stmt)).scalar_one_or_none()

        # Automated checks never produce an Overall verdict — it stays NULL
        # here until expert review finalizes the claim.
        is_finalized = bool(result and result.overall_verdict)
        overall = result.overall_verdict if result else None

        image_url = None
        if submission.submission_type == SubmissionType.PHOTO_CARD and photocard_storage:
            ocr_stmt = select(OcrExtraction).where(
                OcrExtraction.submission_id == submission.id
            )
            ocr = (await session.execute(ocr_stmt)).scalar_one_or_none()
            if ocr:
                image_url = await photocard_storage.get_presigned_url(ocr.image_object_key)

        items.append(
            ExplorerItem(
                submission_id=str(submission.id),
                headline=submission.headline,
                submission_type=submission.submission_type,
                claimed_source_text=submission.claimed_source_text,
                overall_verdict=overall,
                is_finalized=is_finalized,
                source_status=(
                    (result.final_source_status or result.source_status) if result else None
                ),
                content_status=(
                    (result.final_content_status if is_finalized else result.content_status)
                    if result
                    else None
                ),
                date_status=(
                    (result.final_date_status if is_finalized else result.date_status)
                    if result
                    else None
                ),
                confidence=result.confidence if result else None,
                image_url=image_url,
                published_date=submission.published_date,
                created_at=submission.created_at,
            )
        )

    return ExplorerSearchResponse(items=items, total=total, limit=limit, offset=offset,
                                  archive_summary=await repo.explorer_summary())
