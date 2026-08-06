from __future__ import annotations

import logging
import uuid
from datetime import date

from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import ClaimStatus, LogLevel, PipelineStageID, VerificationLabel
from app.features.verification.models import (
    VerificationLog,
    VerificationResult,
    VerificationResultV2,
    VerifiedClaim,
)
from app.shared.base_repository import BaseRepository

logger = logging.getLogger(__name__)


class ClaimRepository(BaseRepository[VerifiedClaim]):

    model_class = VerifiedClaim

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_by_claim_hash(self, claim_hash: str) -> VerifiedClaim | None:
        stmt = (
            select(VerifiedClaim).where(VerifiedClaim.claim_hash == claim_hash).limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_completed_by_hash(self, claim_hash: str) -> VerifiedClaim | None:
        stmt = (
            select(VerifiedClaim)
            .where(
                and_(
                    VerifiedClaim.claim_hash == claim_hash,
                    VerifiedClaim.status == ClaimStatus.COMPLETED,
                )
            )
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def set_status(self, claim_id: uuid.UUID, status: ClaimStatus) -> None:
        stmt = (
            update(VerifiedClaim)
            .where(VerifiedClaim.id == claim_id)
            .values(status=status)
        )
        await self.session.execute(stmt)
        await self.session.flush()
        logger.debug(
            "Claim status updated",
            extra={"claim_id": str(claim_id), "status": status.value},
        )

    async def mark_processing(self, claim_id: uuid.UUID) -> None:
        await self.set_status(claim_id, ClaimStatus.PROCESSING)

    async def mark_completed(self, claim_id: uuid.UUID) -> None:
        await self.set_status(claim_id, ClaimStatus.COMPLETED)

    async def mark_failed(self, claim_id: uuid.UUID) -> None:
        await self.set_status(claim_id, ClaimStatus.FAILED)

    async def get_by_normalized_source(
        self,
        normalized_source: str,
        *,
        status: ClaimStatus | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[VerifiedClaim]:
        conditions = [VerifiedClaim.normalized_source == normalized_source]
        if status is not None:
            conditions.append(VerifiedClaim.status == status)

        stmt = (
            select(VerifiedClaim)
            .where(and_(*conditions))
            .order_by(VerifiedClaim.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_date_range(
        self,
        start_date: date,
        end_date: date,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[VerifiedClaim]:
        stmt = (
            select(VerifiedClaim)
            .where(
                and_(
                    VerifiedClaim.published_date >= start_date,
                    VerifiedClaim.published_date <= end_date,
                )
            )
            .order_by(VerifiedClaim.published_date.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_recent(
        self,
        *,
        status: ClaimStatus | None = ClaimStatus.COMPLETED,
        limit: int = 20,
    ) -> list[VerifiedClaim]:
        stmt = select(VerifiedClaim)
        if status is not None:
            stmt = stmt.where(VerifiedClaim.status == status)
        stmt = stmt.order_by(VerifiedClaim.created_at.desc()).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


class ResultRepository(BaseRepository[VerificationResult]):

    model_class = VerificationResult

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_by_claim_id(self, claim_id: uuid.UUID) -> VerificationResult | None:
        stmt = (
            select(VerificationResult)
            .where(VerificationResult.claim_id == claim_id)
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_results_by_label(
        self,
        label: VerificationLabel,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[VerificationResult]:
        stmt = (
            select(VerificationResult)
            .where(VerificationResult.label == label)
            .order_by(VerificationResult.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def upsert_result(
        self,
        claim_id: uuid.UUID,
        *,
        label: VerificationLabel,
        confidence: float,
        reasoning: str,
        semantic_similarity: float | None,
        entity_match: float | None,
        contradiction_score: float | None,
        keyword_overlap: float | None,
        numerical_consistency: float | None,
        top_article_id: uuid.UUID | None = None,
    ) -> VerificationResult:
        existing = await self.get_by_claim_id(claim_id)

        if existing is not None:
            return await self.update(
                existing,
                label=label,
                confidence=confidence,
                reasoning=reasoning,
                semantic_similarity=semantic_similarity,
                entity_match=entity_match,
                contradiction_score=contradiction_score,
                keyword_overlap=keyword_overlap,
                numerical_consistency=numerical_consistency,
                top_article_id=top_article_id,
            )

        new_result = VerificationResult(
            claim_id=claim_id,
            label=label,
            confidence=confidence,
            reasoning=reasoning,
            semantic_similarity=semantic_similarity,
            entity_match=entity_match,
            contradiction_score=contradiction_score,
            keyword_overlap=keyword_overlap,
            numerical_consistency=numerical_consistency,
            top_article_id=top_article_id,
        )
        return await self.create(new_result)

    # NOTE: log_stage_event/bulk_log/get_logs_for_claim/get_error_logs used to live
    # here but VerificationLog is now submission-scoped (see ResultV2Repository
    # below) since it was repointed off verified_claims during the PDF-schema
    # cutover. This legacy repository is frozen — nothing calls these anymore.


class ResultV2Repository(BaseRepository[VerificationResultV2]):

    model_class = VerificationResultV2

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_by_submission_id(
        self, submission_id: uuid.UUID
    ) -> VerificationResultV2 | None:
        stmt = (
            select(VerificationResultV2)
            .where(VerificationResultV2.submission_id == submission_id)
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_results_by_label(
        self,
        label: VerificationLabel,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[VerificationResultV2]:
        stmt = (
            select(VerificationResultV2)
            .where(VerificationResultV2.final_label == label)
            .order_by(VerificationResultV2.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def upsert_result(
        self,
        submission_id: uuid.UUID,
        *,
        label: VerificationLabel,
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
    ) -> VerificationResultV2:
        existing = await self.get_by_submission_id(submission_id)

        fields = dict(
            final_label=label,
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
        )

        if existing is not None:
            return await self.update(existing, **fields)

        new_result = VerificationResultV2(submission_id=submission_id, **fields)
        return await self.create(new_result)

    async def log_stage_event(
        self,
        submission_id: uuid.UUID,
        stage: PipelineStageID,
        message: str,
        *,
        level: LogLevel = LogLevel.INFO,
        metadata: dict | None = None,
        duration_ms: int | None = None,
    ) -> VerificationLog:
        log_entry = VerificationLog(
            submission_id=submission_id,
            stage=stage,
            level=level,
            message=message,
            metadata_=metadata or {},
            duration_ms=duration_ms,
        )
        self.session.add(log_entry)
        await self.session.flush()
        return log_entry

    async def bulk_log(
        self,
        entries: list[VerificationLog],
    ) -> list[VerificationLog]:
        if not entries:
            return []
        self.session.add_all(entries)
        await self.session.flush()
        return entries

    async def get_logs_for_submission(
        self,
        submission_id: uuid.UUID,
        *,
        stage: PipelineStageID | None = None,
        level: LogLevel | None = None,
        limit: int = 100,
    ) -> list[VerificationLog]:
        conditions = [VerificationLog.submission_id == submission_id]
        if stage is not None:
            conditions.append(VerificationLog.stage == stage)
        if level is not None:
            conditions.append(VerificationLog.level == level)

        stmt = (
            select(VerificationLog)
            .where(and_(*conditions))
            .order_by(VerificationLog.created_at.asc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_error_logs(self, submission_id: uuid.UUID) -> list[VerificationLog]:
        return await self.get_logs_for_submission(
            submission_id, level=LogLevel.ERROR, limit=50
        )
