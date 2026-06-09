"""
app/features/users/router.py
GET /api/v1/users/me          — Get current user profile
PUT /api/v1/users/me          — Update current user profile
GET /api/v1/users/{id}/history — Get verification history for a user
"""
from fastapi import APIRouter
router = APIRouter(prefix="/users", tags=["Users"])
# TODO: Implement user endpoints

