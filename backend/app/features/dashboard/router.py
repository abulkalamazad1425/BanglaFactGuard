from __future__ import annotations

import uuid
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import (
    ContentStatus,
    DateStatus,
    OverallVerdict,
    SourceStatus,
    SubmissionType,
)
from app.features.dashboard.schemas import (
    ExplorerSearchResponse,
    PublicStatsResponse,
    TopSourceItem,
)
from app.features.dashboard.service import DashboardService
from app.shared.dependencies import get_async_session

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


def _service(
    request: Request, session: AsyncSession = Depends(get_async_session)
) -> DashboardService:
    return DashboardService(
        session,
        multimodal_storage=getattr(request.app.state, "multimodal_storage", None),
        photocard_storage=getattr(request.app.state, "photocard_storage", None),
    )


@router.get(
    "/stats", response_model=PublicStatsResponse, summary="Public platform statistics"
)
async def get_public_stats(
    svc: DashboardService = Depends(_service),
) -> PublicStatsResponse:
    return await svc.public_stats()


@router.get(
    "/top-sources",
    response_model=list[TopSourceItem],
    summary="Most frequently claimed sources",
)
async def get_top_sources(
    limit: int = Query(default=10, ge=1, le=50),
    svc: DashboardService = Depends(_service),
) -> list[TopSourceItem]:
    return await svc.top_sources(limit)


@router.get(
    "/explorer",
    response_model=ExplorerSearchResponse,
    summary="Search and browse verified claims (Fact Explorer)",
    description=(
        "Browse and filter verified submissions (in expert review, escalated to "
        "an admin, or finalized; review_state=review lists every claim without "
        "a final decision, including escalated ones) "
        "by keyword, verdict, verification method, publication date range and "
        "news source. Each result links to the full report at "
        "GET /verify/{submission_id}."
    ),
)
async def search_explorer(
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
    svc: DashboardService = Depends(_service),
) -> ExplorerSearchResponse:
    return await svc.explorer(
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
