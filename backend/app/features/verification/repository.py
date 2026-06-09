"""
app/features/verification/repository.py
=========================================
Repositories for the verification feature.

Consolidated from:
  - app/repositories/claim_repository.py  (ClaimRepository)
  - app/repositories/result_repository.py (ResultRepository)
"""

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
    VerifiedClaim,
)
from app.shared.base_repository import BaseRepository

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# ClaimRepository
# ---------------------------------------------------------------------------


class ClaimRepository(BaseRepository[VerifiedClaim]):
    """
    Async repository for VerifiedClaim ORM model.

    Provides cache-hit detection, status lifecycle management, and domain queries.
    """

    model_class = VerifiedClaim

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_by_claim_hash(self, claim_hash: str) -> VerifiedClaim | None:
        """Fetch a claim by its SHA-256 hash (DB-level cache lookup)."""
        stmt = (
            select(VerifiedClaim)
            .where(VerifiedClaim.claim_hash == claim_hash)
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_completed_by_hash(self, claim_hash: str) -> VerifiedClaim | None:
        """Fetch a claim only if it is in COMPLETED status."""
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
        """Update the status of a claim using a direct UPDATE statement."""
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
        """Transition a claim from PENDING to PROCESSING."""
        await self.set_status(claim_id, ClaimStatus.PROCESSING)

    async def mark_completed(self, claim_id: uuid.UUID) -> None:
        """Transition a claim to COMPLETED after successful pipeline run."""
        await self.set_status(claim_id, ClaimStatus.COMPLETED)

    async def mark_failed(self, claim_id: uuid.UUID) -> None:
        """Transition a claim to FAILED after an unrecoverable pipeline error."""
        await self.set_status(claim_id, ClaimStatus.FAILED)

    async def get_by_normalized_source(
        self,
        normalized_source: str,
        *,
        status: ClaimStatus | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[VerifiedClaim]:
        """List claims for a specific canonical source domain."""
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
        """List claims with a published_date within the given range."""
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
        """Return the most recently processed claims."""
        stmt = select(VerifiedClaim)
        if status is not None:
            stmt = stmt.where(VerifiedClaim.status == status)
        stmt = stmt.order_by(VerifiedClaim.created_at.desc()).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


# ---------------------------------------------------------------------------
# ResultRepository
# ---------------------------------------------------------------------------


class ResultRepository(BaseRepository[VerificationResult]):
    """
    Async repository for VerificationResult and VerificationLog ORM models.

    Both tables are always written and read together (Stage 12 / GET /verify/{id}),
    so they are combined in a single repository.
    """

    model_class = VerificationResult

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_by_claim_id(self, claim_id: uuid.UUID) -> VerificationResult | None:
        """Fetch the verification result for a specific claim."""
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
        """Return verification results filtered by verdict label."""
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
        """Insert or update the VerificationResult for a claim."""
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

    async def log_stage_event(
        self,
        claim_id: uuid.UUID,
        stage: PipelineStageID,
        message: str,
        *,
        level: LogLevel = LogLevel.INFO,
        metadata: dict | None = None,
        duration_ms: int | None = None,
    ) -> VerificationLog:
        """Append a single audit log entry for a pipeline stage event."""
        log_entry = VerificationLog(
            claim_id=claim_id,
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
        """Persist multiple log entries in a single flush (Stage 12 batch write)."""
        if not entries:
            return []
        self.session.add_all(entries)
        await self.session.flush()
        return entries

    async def get_logs_for_claim(
        self,
        claim_id: uuid.UUID,
        *,
        stage: PipelineStageID | None = None,
        level: LogLevel | None = None,
        limit: int = 100,
    ) -> list[VerificationLog]:
        """Retrieve audit log entries for a claim, with optional filters."""
        conditions = [VerificationLog.claim_id == claim_id]
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

    async def get_error_logs(self, claim_id: uuid.UUID) -> list[VerificationLog]:
        """Shortcut: retrieve only ERROR-level log entries for a claim."""
        return await self.get_logs_for_claim(
            claim_id, level=LogLevel.ERROR, limit=50
        )
