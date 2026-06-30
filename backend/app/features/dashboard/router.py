"""
app/features/dashboard/router.py
===================================
Public dashboard endpoints — no authentication required.

GET /api/v1/dashboard/stats         — Overall platform statistics
GET /api/v1/dashboard/top-sources   — Most frequently claimed sources
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import VerificationLabel
from app.features.verification.models import VerificationResult, VerifiedClaim
from app.shared.dependencies import get_async_session

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


class PublicStatsResponse(BaseModel):
    total_submissions: int
    true_count: int
    false_count: int
    partially_true_count: int
    not_found_count: int
    pending_count: int


class TopSourceItem(BaseModel):
    source: str
    count: int


@router.get("/stats", response_model=PublicStatsResponse, summary="Public platform statistics")
async def get_public_stats(
    session: AsyncSession = Depends(get_async_session),
) -> PublicStatsResponse:
    """Return aggregate statistics visible to all visitors."""
    from app.core.constants import ClaimStatus

    total = (await session.execute(
        select(func.count()).select_from(VerifiedClaim)
    )).scalar_one()

    pending = (await session.execute(
        select(func.count()).select_from(VerifiedClaim)
        .where(VerifiedClaim.status == ClaimStatus.PENDING)
    )).scalar_one()

    def _lc(lbl: VerificationLabel) -> int:
        return select(func.count()).select_from(VerificationResult).where(
            VerificationResult.label == lbl
        )

    tc = (await session.execute(_lc(VerificationLabel.TRUE))).scalar_one()
    fc = (await session.execute(_lc(VerificationLabel.FALSE))).scalar_one()
    pc = (await session.execute(_lc(VerificationLabel.PARTIALLY_TRUE))).scalar_one()
    nc = (await session.execute(_lc(VerificationLabel.NOT_FOUND_IN_CLAIMED_SOURCE))).scalar_one()

    return PublicStatsResponse(
        total_submissions=total,
        true_count=tc,
        false_count=fc,
        partially_true_count=pc,
        not_found_count=nc,
        pending_count=pending,
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
    """Return the most frequently cited news sources in submissions."""
    stmt = (
        select(VerifiedClaim.claimed_source, func.count().label("cnt"))
        .group_by(VerifiedClaim.claimed_source)
        .order_by(text("cnt DESC"))
        .limit(limit)
    )
    rows = (await session.execute(stmt)).all()
    return [TopSourceItem(source=row[0], count=row[1]) for row in rows]
