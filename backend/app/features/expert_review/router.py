"""
app/features/expert_review/router.py
=======================================
Expert review endpoints.

POST /api/v1/reviews/{claim_id}   — Submit an expert review for a claim
GET  /api/v1/reviews/{claim_id}   — Get review(s) for a claim
PUT  /api/v1/reviews/{review_id}  — Update a review (admin/expert only)
GET  /api/v1/reviews/pending      — List claims awaiting expert review (admin)
"""
from fastapi import APIRouter
router = APIRouter(prefix="/reviews", tags=["Expert Review"])
# TODO: Implement expert review endpoints
