"""
app/features/admin/router.py
GET    /api/v1/admin/users            — List all users
PUT    /api/v1/admin/users/{id}/role  — Assign role to user
GET    /api/v1/admin/stats            — Platform statistics dashboard
DELETE /api/v1/admin/claims/{id}      — Force-delete a claim
"""
from fastapi import APIRouter
router = APIRouter(prefix="/admin", tags=["Admin"])
# TODO: Implement admin endpoints

