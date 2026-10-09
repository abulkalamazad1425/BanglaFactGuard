"""Public dashboard read models: platform statistics, most-claimed sources
and the Fact Explorer listing."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Literal

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
from app.features.dashboard.schemas import (
    ExplorerItem,
    ExplorerSearchResponse,
    MethodDistribution,
    PublicStatsResponse,
    TopSourceItem,
)
from app.features.multimodal.models import MultimodalAnalysis
from app.features.multimodal.storage_service import MultimodalStorageService
from app.features.photocard.storage_service import PhotoCardStorageService
from app.features.submissions.models import PhotocardExtraction, Submission
from app.features.submissions.repository import SubmissionRepository
from app.features.verification.headline_status import headline_status_for_result
from app.features.verification.models import VerificationResult
from app.features.verification.presenter import is_headline_result
from app.shared.base_repository import rows_by_submission


class DashboardService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        multimodal_storage: MultimodalStorageService | None = None,
        photocard_storage: PhotoCardStorageService | None = None,
    ) -> None:
        self._session = session
        self._multimodal_storage = multimodal_storage
        self._photocard_storage = photocard_storage

    async def public_stats(self) -> PublicStatsResponse:
        session = self._session
        # Two aggregate queries (conditional counts) instead of one query per number.
        submission_counts = (
            await session.execute(
                select(
                    func.count(),
                    func.count().filter(
                        Submission.status.in_((SubmissionStatus.PENDING, SubmissionStatus.PROCESSING))
                    ),
                    func.count().filter(Submission.submission_type == SubmissionType.SOURCE_BASED),
                    func.count().filter(Submission.submission_type == SubmissionType.MULTIMODAL),
                    func.count().filter(Submission.submission_type == SubmissionType.PHOTO_CARD),
                ).select_from(Submission)
            )
        ).one()
        total, pending, source_based_c, multimodal_c, photo_card_c = submission_counts

        result_counts = (
            await session.execute(
                select(
                    func.count().filter(VerificationResult.source_status == SourceStatus.CONFIRMED),
                    func.count().filter(VerificationResult.source_status == SourceStatus.NOT_FOUND),
                    func.count().filter(VerificationResult.content_status == ContentStatus.MATCHED),
                    func.count().filter(VerificationResult.content_status == ContentStatus.ALTERED),
                    func.count().filter(VerificationResult.date_status == DateStatus.MATCHED),
                    func.count().filter(VerificationResult.date_status == DateStatus.MISMATCHED),
                    # AVG ignores NULL, exactly like the former `IS NOT NULL` filter.
                    func.avg(VerificationResult.avg_verification_time_ms),
                ).select_from(VerificationResult)
            )
        ).one()
        (
            source_confirmed, source_not_found, content_matched, content_altered,
            date_matched, date_mismatched, avg_ms,
        ) = result_counts
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

    async def top_sources(self, limit: int) -> list[TopSourceItem]:
        stmt = (
            select(Submission.claimed_source_text, func.count().label("cnt"))
            .where(Submission.claimed_source_text.is_not(None))
            .group_by(Submission.claimed_source_text)
            .order_by(text("cnt DESC"))
            .limit(limit)
        )
        rows = (await self._session.execute(stmt)).all()
        return [TopSourceItem(source=row[0], count=row[1]) for row in rows]

    async def explorer(
        self,
        *,
        keyword: str | None,
        source_status: SourceStatus | None,
        content_status: ContentStatus | None,
        date_status: DateStatus | None,
        overall_verdict: OverallVerdict | None,
        method: SubmissionType | None,
        date_from: date | None,
        date_to: date | None,
        source_id: uuid.UUID | None,
        review_state: Literal["finalized", "review"] | None,
        limit: int,
        offset: int,
    ) -> ExplorerSearchResponse:
        session = self._session
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

        multimodal_storage = self._multimodal_storage
        photocard_storage = self._photocard_storage

        multimodal_by_sub = await rows_by_submission(
            session, MultimodalAnalysis,
            [s.id for s in rows if s.submission_type == SubmissionType.MULTIMODAL],
        )
        results_by_sub = await rows_by_submission(
            session, VerificationResult,
            [s.id for s in rows if s.submission_type != SubmissionType.MULTIMODAL],
        )
        extractions_by_sub = (
            await rows_by_submission(
                session, PhotocardExtraction,
                [s.id for s in rows if s.submission_type == SubmissionType.PHOTO_CARD],
            )
            if photocard_storage
            else {}
        )

        items = []
        for submission in rows:
            if submission.submission_type == SubmissionType.MULTIMODAL:
                mm = multimodal_by_sub.get(submission.id)

                image_url = (
                    await multimodal_storage.get_presigned_url(mm.image_object_key)
                    if mm and multimodal_storage
                    else None
                )
                overall = mm.expert_overall_verdict if mm else None
                items.append(
                    ExplorerItem(
                        submission_id=str(submission.id),
                        headline=submission.headline,
                        submission_type=submission.submission_type,
                        claimed_source_text=None,
                        overall_verdict=overall,
                        prediction=mm.prediction if mm else None,
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

            result = results_by_sub.get(submission.id)

            # Automated checks never produce an Overall verdict — it stays NULL
            # here until expert review finalizes the claim.
            is_finalized = bool(result and result.overall_verdict)
            overall = result.overall_verdict if result else None

            image_url = None
            if submission.submission_type == SubmissionType.PHOTO_CARD and photocard_storage:
                extraction = extractions_by_sub.get(submission.id)
                if extraction:
                    image_url = await photocard_storage.get_presigned_url(extraction.image_object_key)

            items.append(
                ExplorerItem(
                    submission_id=str(submission.id),
                    headline=submission.headline,
                    submission_type=submission.submission_type,
                    claimed_source_text=submission.claimed_source_text,
                    overall_verdict=overall,
                    is_finalized=is_finalized,
                    source_status=result.source_status if result else None,
                    content_status=(result.content_status if result and is_headline_result(result) else None),
                    headline_status=headline_status_for_result(result, claim_headline=submission.headline),
                    date_status=result.date_status if result else None,
                    confidence=result.confidence if result else None,
                    image_url=image_url,
                    published_date=submission.published_date,
                    created_at=submission.created_at,
                )
            )

        return ExplorerSearchResponse(items=items, total=total, limit=limit, offset=offset,
                                      archive_summary=await repo.explorer_summary())
