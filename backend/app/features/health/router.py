"""
app/features/health/router.py
================================
Health check endpoints.

Migrated from: app/api/v1/endpoints/health.py
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from app.db.engine import AsyncSessionLocal
from app.services.cache_service import CacheService
from app.api.dependencies import get_cache_service

router = APIRouter(tags=["Health"])


class HealthResponse(BaseModel):
    status: str
    version: str = "1.0.0"


class ReadinessResponse(BaseModel):
    status: str
    database: str
    redis: str


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Liveness probe",
    description="Returns 200 if the application process is running.",
)
async def liveness() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get(
    "/health/ready",
    response_model=ReadinessResponse,
    summary="Readiness probe",
    description="Checks database and Redis connectivity. Returns 503 if either is unavailable.",
)
async def readiness(
    cache: CacheService = Depends(get_cache_service),
) -> ReadinessResponse:
    from fastapi import HTTPException

    # Check PostgreSQL
    db_status = "ok"
    try:
        async with AsyncSessionLocal() as session:
            from sqlalchemy import text
            await session.execute(text("SELECT 1"))
    except Exception as exc:
        db_status = f"error: {exc}"

    # Check Redis
    redis_status = "ok" if await cache.health_check() else "error: unreachable"

    if "error" in db_status or "error" in redis_status:
        raise HTTPException(
            status_code=503,
            detail={"status": "degraded", "database": db_status, "redis": redis_status},
        )

    return ReadinessResponse(status="ready", database=db_status, redis=redis_status)
