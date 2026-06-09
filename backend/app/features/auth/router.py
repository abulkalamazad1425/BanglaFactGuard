"""
app/features/auth/router.py
==============================
Authentication API endpoints.

POST /api/v1/auth/register           — Create a new user account
POST /api/v1/auth/login              — Authenticate and receive JWT pair
POST /api/v1/auth/refresh            — Rotate refresh token
POST /api/v1/auth/logout             — Revoke refresh token
GET  /api/v1/auth/me                 — Get current user profile
POST /api/v1/auth/password-reset/request  — Send reset email
POST /api/v1/auth/password-reset/confirm  — Apply new password with token
GET  /api/v1/auth/verify-email/{token}    — Confirm email address
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/auth", tags=["Authentication"])

# TODO: Implement authentication endpoints
# This file is a placeholder — full implementation pending AuthService.
