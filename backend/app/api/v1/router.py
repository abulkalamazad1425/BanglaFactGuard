
from __future__ import annotations

from fastapi import APIRouter

from app.features.admin.router import router as admin_router
from app.features.auth.router import router as auth_router
from app.features.dashboard.router import router as dashboard_router
from app.features.expert_review.router import router as expert_review_router
from app.features.feedback.router import router as feedback_router
from app.features.health.router import router as health_router
from app.features.multimodal.router import router as multimodal_router
from app.features.notifications.router import router as notifications_router
from app.features.sources.router import router as sources_router
from app.features.users.router import router as users_router
from app.features.verification.router import router as verification_router

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(admin_router)
api_router.include_router(auth_router)
api_router.include_router(dashboard_router)
api_router.include_router(expert_review_router)
api_router.include_router(feedback_router)
api_router.include_router(health_router)
api_router.include_router(multimodal_router)
api_router.include_router(notifications_router)
api_router.include_router(sources_router)
api_router.include_router(users_router)
api_router.include_router(verification_router)
