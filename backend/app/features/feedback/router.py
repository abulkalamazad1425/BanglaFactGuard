"""
app/features/feedback/router.py
POST /api/v1/feedback/{claim_id}  — Submit feedback for a verification result
GET  /api/v1/feedback/{claim_id}  — Get feedback for a claim (admin)
"""

from fastapi import APIRouter

router = APIRouter(prefix="/feedback", tags=["User Feedback"])
