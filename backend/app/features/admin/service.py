"""
app/features/admin/service.py
================================
Admin service: expert account management and platform statistics.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.constants import ClaimStatus, VerificationLabel
from app.core.exceptions import DuplicateRecordError, RecordNotFoundError, WeakPasswordError
from app.features.admin.schemas import (
    AdminStatsResponse,
    CreateExpertRequest,
    ExpertResponse,
    ResetExpertPasswordRequest,
    UpdateExpertRequest,
    VerdictBreakdown,
)
from app.features.auth.models import User
from app.features.auth.repository import RefreshTokenRepository, UserRepository
from app.features.auth.security import hash_password
from app.features.expert_review.models import CredibilityScore
from app.features.expert_review.repository import CredibilityScoreRepository
from app.features.users.models import UserProfile
from app.features.verification.models import VerificationResult, VerifiedClaim

logger = structlog.get_logger(__name__)
_SETTINGS = get_settings()


def _validate_password(password: str) -> None:
    """Reuse password strength rules from auth."""
    from app.features.auth.service import _validate_password_strength
    _validate_password_strength(password)


class AdminService:
    """Handles admin-level operations: expert management and statistics."""

    def __init__(
        self,
        session: AsyncSession,
        user_repo: UserRepository,
        credibility_repo: CredibilityScoreRepository,
        token_repo: RefreshTokenRepository,
    ) -> None:
        self._session = session
        self._users = user_repo
        self._credibility = credibility_repo
        self._tokens = token_repo

    # ------------------------------------------------------------------
    # Expert management
    # ------------------------------------------------------------------

    async def create_expert(self, req: CreateExpertRequest) -> ExpertResponse:
        """
        Create a new expert user account.
        Admin sets the initial credentials. The expert can change their
        password later via the change-password endpoint.
        """
        _validate_password(req.password)

        if await self._users.email_exists(req.email):
            raise DuplicateRecordError(model="User", field="email", value=req.email)

        user = User(
            email=req.email,
            hashed_password=hash_password(req.password),
            full_name=req.full_name,
            role="expert",
            is_active=True,
            is_verified=True,  # Admin-created accounts are pre-verified
        )
        user = await self._users.create(user)

        # Create profile with expertise area
        profile = UserProfile(
            user_id=user.id,
            bio=req.expertise_area,
        )
        self._session.add(profile)

        # Initialize credibility score
        cred = CredibilityScore(
            user_id=user.id,
            score=_SETTINGS.auth.initial_expert_credibility,
            total_votes=0,
            correct_votes=0,
        )
        self._session.add(cred)
        await self._session.flush()

        logger.info("expert_created", user_id=str(user.id), email=req.email)
        return _expert_to_response(user, req.expertise_area, _SETTINGS.auth.initial_expert_credibility, 0)

    async def list_experts(self, *, limit: int = 50, offset: int = 0) -> list[ExpertResponse]:
        """Return all expert accounts with their credibility scores."""
        users = await self._users.list_by_role("expert", limit=limit, offset=offset)
        results = []
        for u in users:
            cred = await self._credibility.get_by_user_id(u.id)
            profile_stmt = select(UserProfile).where(UserProfile.user_id == u.id).limit(1)
            profile_result = await self._session.execute(profile_stmt)
            profile = profile_result.scalar_one_or_none()
            results.append(_expert_to_response(
                u,
                expertise_area=profile.bio if profile else None,
                credibility_score=cred.score if cred else None,
                total_votes=cred.total_votes if cred else 0,
            ))
        return results

    async def get_expert(self, user_id: uuid.UUID) -> ExpertResponse:
        """Return a single expert's details."""
        user = await self._users.get_by_id(user_id)
        if user.role != "expert":
            raise RecordNotFoundError(model="Expert", identifier=str(user_id))
        cred = await self._credibility.get_by_user_id(user_id)
        profile_stmt = select(UserProfile).where(UserProfile.user_id == user_id).limit(1)
        profile_result = await self._session.execute(profile_stmt)
        profile = profile_result.scalar_one_or_none()
        return _expert_to_response(
            user,
            expertise_area=profile.bio if profile else None,
            credibility_score=cred.score if cred else None,
            total_votes=cred.total_votes if cred else 0,
        )

    async def update_expert(self, user_id: uuid.UUID, req: UpdateExpertRequest) -> ExpertResponse:
        """Update an expert's profile (name, email, expertise, active status)."""
        user = await self._users.get_by_id(user_id)
        updates: dict = {}
        if req.full_name is not None:
            updates["full_name"] = req.full_name
        if req.email is not None and req.email != user.email:
            if await self._users.email_exists(req.email):
                raise DuplicateRecordError(model="User", field="email", value=req.email)
            updates["email"] = req.email
        if req.is_active is not None:
            updates["is_active"] = req.is_active
        if updates:
            user = await self._users.update(user, **updates)

        # Update expertise area in profile
        if req.expertise_area is not None:
            profile_stmt = select(UserProfile).where(UserProfile.user_id == user_id).limit(1)
            profile_result = await self._session.execute(profile_stmt)
            profile = profile_result.scalar_one_or_none()
            if profile:
                profile.bio = req.expertise_area
                self._session.add(profile)
                await self._session.flush()

        cred = await self._credibility.get_by_user_id(user_id)
        return _expert_to_response(
            user,
            expertise_area=req.expertise_area,
            credibility_score=cred.score if cred else None,
            total_votes=cred.total_votes if cred else 0,
        )

    async def reset_expert_password(
        self, user_id: uuid.UUID, req: ResetExpertPasswordRequest
    ) -> dict:
        """Admin force-resets an expert's password and revokes all their tokens."""
        _validate_password(req.new_password)
        user = await self._users.get_by_id(user_id)
        if user.role not in ("expert", "admin"):
            raise RecordNotFoundError(model="Expert", identifier=str(user_id))
        user.hashed_password = hash_password(req.new_password)
        self._session.add(user)
        await self._tokens.revoke_all_for_user(user_id)
        await self._session.flush()
        logger.info("expert_password_reset_by_admin", user_id=str(user_id))
        return {"message": "Password has been reset. The expert must log in again."}

    async def deactivate_expert(self, user_id: uuid.UUID) -> ExpertResponse:
        """Deactivate an expert account (prevents login)."""
        user = await self._users.update(await self._users.get_by_id(user_id), is_active=False)
        await self._tokens.revoke_all_for_user(user_id)
        return await self.get_expert(user_id)

    async def activate_expert(self, user_id: uuid.UUID) -> ExpertResponse:
        """Re-activate a previously deactivated expert account."""
        await self._users.update(await self._users.get_by_id(user_id), is_active=True)
        return await self.get_expert(user_id)

    # ------------------------------------------------------------------
    # Platform statistics
    # ------------------------------------------------------------------

    async def get_platform_stats(self) -> AdminStatsResponse:
        """Aggregate platform-wide metrics for the admin dashboard."""
        thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)

        # Total submissions
        total_stmt = select(func.count()).select_from(VerifiedClaim)
        total = (await self._session.execute(total_stmt)).scalar_one()

        # Last 30 days
        recent_stmt = select(func.count()).select_from(VerifiedClaim).where(
            VerifiedClaim.created_at >= thirty_days_ago
        )
        recent = (await self._session.execute(recent_stmt)).scalar_one()

        # Verdict breakdown
        def _count_label(lbl: VerificationLabel):
            return select(func.count()).select_from(VerificationResult).where(
                VerificationResult.label == lbl
            )

        true_c = (await self._session.execute(_count_label(VerificationLabel.TRUE))).scalar_one()
        false_c = (await self._session.execute(_count_label(VerificationLabel.FALSE))).scalar_one()
        partial_c = (await self._session.execute(_count_label(VerificationLabel.PARTIALLY_TRUE))).scalar_one()
        nf_c = (await self._session.execute(_count_label(VerificationLabel.NOT_FOUND_IN_CLAIMED_SOURCE))).scalar_one()

        # Expert counts
        total_experts = await self._users.count_by_role("expert")
        active_experts_stmt = select(func.count()).select_from(User).where(
            User.role == "expert", User.is_active.is_(True)
        )
        active_experts = (await self._session.execute(active_experts_stmt)).scalar_one()

        # Pending expert reviews
        from app.features.expert_review.models import ExpertReview
        pending_stmt = select(func.count()).select_from(ExpertReview).where(
            ExpertReview.status == "pending"
        )
        pending = (await self._session.execute(pending_stmt)).scalar_one()

        return AdminStatsResponse(
            total_submissions=total,
            submissions_last_30_days=recent,
            verdict_breakdown=VerdictBreakdown(
                true_count=true_c,
                false_count=false_c,
                partially_true_count=partial_c,
                not_found_count=nf_c,
            ),
            pending_expert_reviews=pending,
            total_experts=total_experts,
            active_experts=active_experts,
            avg_verification_time_seconds=None,  # Future: compute from created_at diff
        )


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _expert_to_response(
    user: User,
    expertise_area: str | None,
    credibility_score: float | None,
    total_votes: int,
) -> ExpertResponse:
    return ExpertResponse(
        id=str(user.id),
        full_name=user.full_name,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        expertise_area=expertise_area,
        credibility_score=credibility_score,
        total_votes=total_votes,
    )
