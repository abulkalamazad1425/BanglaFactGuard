from __future__ import annotations

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import ContentStatus, DateStatus, SourceStatus
from app.features.verification.models import VerificationResult
from app.shared.base_repository import BaseRepository

logger = logging.getLogger(__name__)


class ResultRepository(BaseRepository[VerificationResult]):

    model_class = VerificationResult

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_by_submission_id(
        self, submission_id: uuid.UUID
    ) -> VerificationResult | None:
        stmt = (
            select(VerificationResult)
            .where(VerificationResult.submission_id == submission_id)
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_results_by_source_status(
        self,
        source_status: SourceStatus,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[VerificationResult]:
        stmt = (
            select(VerificationResult)
            .where(VerificationResult.source_status == source_status)
            .order_by(VerificationResult.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def upsert_result(
        self,
        submission_id: uuid.UUID,
        *,
        source_status: SourceStatus | None,
        content_status: ContentStatus | None,
        date_status: DateStatus | None,
        confidence: float,
        reasoning: str,
        semantic_similarity: float | None,
        entity_match: float | None,
        contradiction_score: float | None,
        keyword_overlap: float | None,
        numerical_consistency: float | None,
        top_article_id: uuid.UUID | None = None,
        ai_preliminary_label: str | None = None,
        avg_verification_time_ms: int | None = None,
        manipulation_flags: dict | None = None,
        headline_similarity: float | None = None,
        body_similarity: float | None = None,
        passage_similarity: float | None = None,
        headline_keyword_coverage: float | None = None,
        passage_keyword_coverage: float | None = None,
        body_keyword_coverage: float | None = None,
        claim_scope: str | None = None,
        pipeline_version: str | None = None,
        analysis_details: dict | None = None,
        reused_from_submission_id: uuid.UUID | None = None,
    ) -> VerificationResult:
        """Write the AUTOMATED snapshot for a submission.

        Only automated columns are written here. Expert-finalized columns
        (final_*, overall_verdict, finalized_at) belong to ExpertReviewService
        and are never touched, and `ai_consensus_label` is no longer written
        at all: the automated system casts no overall truth vote.
        """
        existing = await self.get_by_submission_id(submission_id)

        fields = dict(
            source_status=source_status,
            content_status=content_status,
            date_status=date_status,
            confidence=confidence,
            reasoning=reasoning,
            semantic_similarity=semantic_similarity,
            entity_match=entity_match,
            contradiction_score=contradiction_score,
            keyword_overlap=keyword_overlap,
            numerical_consistency=numerical_consistency,
            top_article_id=top_article_id,
            ai_preliminary_label=ai_preliminary_label,
            avg_verification_time_ms=avg_verification_time_ms,
            manipulation_flags=manipulation_flags,
            headline_similarity=headline_similarity,
            body_similarity=body_similarity,
            passage_similarity=passage_similarity,
            headline_keyword_coverage=headline_keyword_coverage,
            passage_keyword_coverage=passage_keyword_coverage,
            body_keyword_coverage=body_keyword_coverage,
            claim_scope=claim_scope,
            pipeline_version=pipeline_version,
            analysis_details=analysis_details,
            reused_from_submission_id=reused_from_submission_id,
        )

        if existing is not None:
            return await self.update(existing, **fields)

        new_result = VerificationResult(submission_id=submission_id, **fields)
        return await self.create(new_result)
