"""
app/api/v1/router.py
======================
Aggregates all v1 feature routers into a single APIRouter.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.features.health.router import router as health_router
from app.features.multimodal.router import router as multimodal_router
from app.features.sources.router import router as sources_router
from app.features.verification.router import router as verification_router

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(health_router)
api_router.include_router(verification_router)
api_router.include_router(sources_router)
api_router.include_router(multimodal_router)
