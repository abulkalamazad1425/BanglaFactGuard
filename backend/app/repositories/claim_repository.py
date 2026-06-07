"""
app/repositories/claim_repository.py
======================================
Repository for the `verified_claims` table.

Provides domain-specific query methods for:
- Cache-hit detection via `claim_hash` (Stage 2).
- Status lifecycle management (pending → processing → completed/failed).
- Querying claims by source domain or date range (analytics endpoints).

This repository is the most frequently accessed in the pipeline:
every verification request touches it at least once (Stage 2 cache check)
and again in Stage 12 (persistence).
"""

from __future__ import annotations

import logging
import uuid
from datetime import date

from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import ClaimStatus
from app.models.verified_claim import VerifiedClaim
from app.repositories.base import BaseRepository

logger = logging.getLogger(__name__)


class ClaimRepository(BaseRepository[VerifiedClaim]):
    """
    Async repository for VerifiedClaim ORM model.

    Inherits standard CRUD from BaseRepository and adds claim-specific
    query methods used by VerificationService and Stage 2/12.
    """

    model_class = VerifiedClaim

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    # ------------------------------------------------------------------
    # Cache-hit detection (Stage 2)
    # ------------------------------------------------------------------

    async def get_by_claim_hash(self, claim_hash: str) -> VerifiedClaim | None:
        """
        Fetch a claim by its SHA-256 hash (DB-level cache lookup).

        This is the primary Stage 2 DB-cache check. If a completed claim
        with this hash exists, the pipeline returns its cached result
        without re-running Stages 3–12.

        Args:
            claim_hash: SHA-256 hex digest of normalised (headline + claimed_source).

        Returns:
            Matching VerifiedClaim instance or None (cache miss).
        """
        stmt = (
            select(VerifiedClaim)
            .where(VerifiedClaim.claim_hash == claim_hash)
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_completed_by_hash(self, claim_hash: str) -> VerifiedClaim | None:
        """
        Fetch a claim only if it is in COMPLETED status.

        Used specifically for the DB-layer cache hit — a PENDING or PROCESSING
        claim with the same hash should NOT be returned as a cache hit.

        Args:
            claim_hash: SHA-256 hex digest.

        Returns:
            Completed VerifiedClaim or None.
        """
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

    # ------------------------------------------------------------------
    # Status lifecycle
    # ------------------------------------------------------------------

    async def set_status(
        self,
        claim_id: uuid.UUID,
        status: ClaimStatus,
    ) -> None:
        """
        Update the status of a claim using a direct UPDATE statement.

        Preferred over `update()` for status changes because it avoids
        fetching the full row first — important for high-throughput
        stage transitions (PENDING → PROCESSING → COMPLETED).

        Args:
            claim_id: UUID of the claim to update.
            status:   New ClaimStatus value.
        """
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

    # ------------------------------------------------------------------
    # Domain queries
    # ------------------------------------------------------------------

    async def get_by_normalized_source(
        self,
        normalized_source: str,
        *,
        status: ClaimStatus | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[VerifiedClaim]:
        """
        List claims for a specific canonical source domain.

        Args:
            normalized_source: Canonical domain (e.g. "prothomalo.com").
            status:            Optional status filter.
            limit:             Max records to return.
            offset:            Records to skip.

        Returns:
            List of matching VerifiedClaim instances ordered by created_at DESC.
        """
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
        """
        List claims with a published_date within the given range.

        Used for analytics dashboards and reporting endpoints.

        Args:
            start_date: Inclusive start date.
            end_date:   Inclusive end date.
            limit:      Max records to return.
            offset:     Records to skip.

        Returns:
            List of VerifiedClaim instances ordered by published_date DESC.
        """
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
        """
        Return the most recently processed claims.

        Args:
            status: Filter by status (defaults to COMPLETED). Pass None for all.
            limit:  Number of records to return.

        Returns:
            List of VerifiedClaim instances, newest first.
        """
        stmt = select(VerifiedClaim)
        if status is not None:
            stmt = stmt.where(VerifiedClaim.status == status)
        stmt = stmt.order_by(VerifiedClaim.created_at.desc()).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
