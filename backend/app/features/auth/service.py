"""
app/features/auth/service.py
==============================
Authentication service: registration, login, JWT issuance, token refresh.

Planned implementation:
- bcrypt password hashing via passlib
- JWT access tokens via python-jose (RS256 / HS256)
- Refresh token rotation with DB-backed revocation list
- Email verification flow (token sent via notification service)
- OAuth2 social login support (Google, Facebook)
"""

from __future__ import annotations

# TODO: Implement AuthService
# Placeholder file — full implementation pending.


class AuthService:
    """
    Handles user registration, authentication, and JWT lifecycle.

    Dependencies (to be injected):
        user_repo:         UserRepository (reads/writes users table)
        token_repo:        RefreshTokenRepository
        notification_svc:  NotificationService (sends verification emails)
        settings:          AppSettings (JWT secret, token TTLs)
    """

    pass
