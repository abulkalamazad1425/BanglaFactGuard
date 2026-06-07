"""
app/api/v1/router.py
======================
Aggregates all v1 endpoint routers into a single APIRouter.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.endpoints import health, sources, verification

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(health.router)
api_router.include_router(verification.router)
api_router.include_router(sources.router)
