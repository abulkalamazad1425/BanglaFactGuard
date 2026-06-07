"""
app/repositories/result_repository.py
=======================================
Repository for the `verification_results` and `verification_logs` tables.

Combines two closely related tables in a single repository because:
1. Both are always written together in Stage 12 (Persistence).
2. Both are always read together in the GET /verify/{id} response.
3. They share the same `claim_id` FK and have no independent access patterns.

This avoids an extra file and DI binding for the logs table while keeping
the service layer from dealing with raw DB operations on two tables.
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import LogLevel, PipelineStageID, VerificationLabel
from app.models.verification_log import VerificationLog
from app.models.verification_result import VerificationResult
from app.repositories.base import BaseRepository

logger = logging.getLogger(__name__)


class ResultRepository(BaseRepository[VerificationResult]):
    """
    Async repository for VerificationResult and VerificationLog ORM models.

    The primary model is VerificationResult (inheriting base CRUD from
    BaseRepository). Log-specific write methods are appended as domain methods.
    """

    model_class = VerificationResult

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    # ------------------------------------------------------------------
    # VerificationResult queries
    # ------------------------------------------------------------------

    async def get_by_claim_id(self, claim_id: uuid.UUID) -> VerificationResult | None:
        """
        Fetch the verification result for a specific claim.

        Returns None if the claim exists but has not yet been completed
        (e.g. PENDING or PROCESSING status).

        Args:
            claim_id: UUID of the parent verified_claim.

        Returns:
            VerificationResult instance or None.
        """
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
        """
        Return verification results filtered by verdict label.

        Used by analytics dashboards to surface e.g. all FALSE verdicts.

        Args:
            label:  The verdict label to filter by.
            limit:  Max records to return.
            offset: Records to skip.

        Returns:
            List of VerificationResult instances ordered by created_at DESC.
        """
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
        """
        Insert or update the VerificationResult for a claim.

        Uses an INSERT-or-UPDATE pattern: if a result already exists for this
        claim (e.g. from a previous failed run), it is updated in-place rather
        than creating a duplicate (the DB UNIQUE constraint on claim_id enforces
        the one-to-one relationship).

        Args:
            claim_id:              UUID of the parent claim.
            label:                 Final verdict label.
            confidence:            Overall confidence score.
            reasoning:             Human-readable explanation.
            semantic_similarity:   Stage 8 similarity score.
            entity_match:          Stage 8 entity overlap score.
            contradiction_score:   Stage 9 NLI contradiction score.
            keyword_overlap:       Stage 8 keyword overlap score.
            numerical_consistency: Stage 8 numeral consistency score.
            top_article_id:        FK to the best evidence article.

        Returns:
            The created or updated VerificationResult instance.
        """
        existing = await self.get_by_claim_id(claim_id)

        if existing is not None:
            # Update in-place (re-verification or force_refresh scenario)
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

        # Create new result
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

    # ------------------------------------------------------------------
    # VerificationLog writes
    # ------------------------------------------------------------------

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
        """
        Append a single audit log entry for a pipeline stage event.

        This is the primary write path for all stage-level logging.
        Called by Stage 12 in batch, but also by individual stages on ERROR
        or WARNING to ensure critical failures are persisted immediately.

        Args:
            claim_id:    UUID of the parent claim.
            stage:       The PipelineStageID that emitted this event.
            message:     Short human-readable description.
            level:       Severity (INFO, WARNING, ERROR).
            metadata:    Optional JSONB payload for debug detail.
            duration_ms: Stage execution time up to this log point.

        Returns:
            The persisted VerificationLog instance.
        """
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
        """
        Persist multiple log entries in a single flush (Stage 12 batch write).

        Args:
            entries: Pre-constructed VerificationLog instances.

        Returns:
            The persisted log entries.
        """
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
        """
        Retrieve audit log entries for a claim, with optional filters.

        Args:
            claim_id: UUID of the parent claim.
            stage:    Optional filter by pipeline stage.
            level:    Optional filter by log severity.
            limit:    Max entries to return.

        Returns:
            List of VerificationLog instances ordered by created_at ASC.
        """
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
        """
        Shortcut to retrieve only ERROR-level log entries for a claim.

        Used when displaying why a verification failed in the status endpoint.

        Args:
            claim_id: UUID of the parent claim.

        Returns:
            List of ERROR VerificationLog entries, chronological.
        """
        return await self.get_logs_for_claim(
            claim_id, level=LogLevel.ERROR, limit=50
        )
