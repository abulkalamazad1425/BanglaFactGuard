from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.constants import SubmissionStatus, VerificationLabel
from app.core.exceptions import (
    DuplicateRecordError,
    RecordNotFoundError,
    WeakPasswordError,
)
from app.features.admin.schemas import (
    AdminStatsResponse,
    CreateExpertRequest,
    CredibilityWeightTierRequest,
    CredibilityWeightTierResponse,
    CredibilityWeightTierUpdateRequest,
    ExpertResponse,
    ResetExpertPasswordRequest,
    UpdateExpertRequest,
    VerdictBreakdown,
)
from app.features.auth.models import User
from app.features.auth.repository import RefreshTokenRepository, UserRepository
from app.features.auth.security import hash_password
from app.features.expert_review.models import CredibilityWeightTier
from app.features.expert_review.repository import (
    CredibilityWeightTierRepository,
    ExpertProfileRepository,
)
from app.features.submissions.models import Submission
from app.features.verification.models import VerificationResultV2

logger = structlog.get_logger(__name__)
_SETTINGS = get_settings()


def _validate_password(password: str) -> None:
    from app.features.auth.service import _validate_password_strength

    _validate_password_strength(password)


class AdminService:

    def __init__(
        self,
        session: AsyncSession,
        user_repo: UserRepository,
        profile_repo: ExpertProfileRepository,
        tier_repo: CredibilityWeightTierRepository,
        token_repo: RefreshTokenRepository,
    ) -> None:
        self._session = session
        self._users = user_repo
        self._profiles = profile_repo
        self._tiers = tier_repo
        self._tokens = token_repo

    async def create_expert(self, req: CreateExpertRequest) -> ExpertResponse:
        _validate_password(req.password)

        if await self._users.email_exists(req.email):
            raise DuplicateRecordError(model="User", field="email", value=req.email)

        user = User(
            email=req.email,
            hashed_password=hash_password(req.password),
            full_name=req.full_name,
            role="expert",
            is_active=True,
            is_verified=True,
        )
        user = await self._users.create(user)

        profile = await self._profiles.get_or_create(
            user.id,
            initial_score=_SETTINGS.auth.initial_expert_credibility,
            area_of_expertise=req.expertise_area or "General",
        )

        logger.info("expert_created", user_id=str(user.id), email=req.email)
        return _expert_to_response(
            user, profile.area_of_expertise, profile.credibility_score, 0
        )

    async def list_experts(
        self, *, limit: int = 50, offset: int = 0
    ) -> list[ExpertResponse]:
        users = await self._users.list_by_role("expert", limit=limit, offset=offset)
        results = []
        for u in users:
            profile = await self._profiles.get_by_user_id(u.id)
            results.append(
                _expert_to_response(
                    u,
                    expertise_area=profile.area_of_expertise if profile else None,
                    credibility_score=profile.credibility_score if profile else None,
                    total_votes=profile.total_votes if profile else 0,
                )
            )
        return results

    async def get_expert(self, user_id: uuid.UUID) -> ExpertResponse:
        user = await self._users.get_by_id(user_id)
        if user.role != "expert":
            raise RecordNotFoundError(model="Expert", identifier=str(user_id))
        profile = await self._profiles.get_by_user_id(user_id)
        return _expert_to_response(
            user,
            expertise_area=profile.area_of_expertise if profile else None,
            credibility_score=profile.credibility_score if profile else None,
            total_votes=profile.total_votes if profile else 0,
        )

    async def update_expert(
        self, user_id: uuid.UUID, req: UpdateExpertRequest
    ) -> ExpertResponse:
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

        profile = await self._profiles.get_by_user_id(user_id)
        if req.expertise_area is not None and profile is not None:
            profile = await self._profiles.update(
                profile, area_of_expertise=req.expertise_area
            )

        return _expert_to_response(
            user,
            expertise_area=profile.area_of_expertise if profile else req.expertise_area,
            credibility_score=profile.credibility_score if profile else None,
            total_votes=profile.total_votes if profile else 0,
        )

    async def reset_expert_password(
        self, user_id: uuid.UUID, req: ResetExpertPasswordRequest
    ) -> dict:
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
        user = await self._users.update(
            await self._users.get_by_id(user_id), is_active=False
        )
        await self._tokens.revoke_all_for_user(user_id)
        return await self.get_expert(user_id)

    async def activate_expert(self, user_id: uuid.UUID) -> ExpertResponse:
        await self._users.update(await self._users.get_by_id(user_id), is_active=True)
        return await self.get_expert(user_id)

    async def get_platform_stats(self) -> AdminStatsResponse:
        thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)

        total_stmt = select(func.count()).select_from(Submission)
        total = (await self._session.execute(total_stmt)).scalar_one()

        recent_stmt = (
            select(func.count())
            .select_from(Submission)
            .where(Submission.created_at >= thirty_days_ago)
        )
        recent = (await self._session.execute(recent_stmt)).scalar_one()

        def _count_label(lbl: VerificationLabel):
            return (
                select(func.count())
                .select_from(VerificationResultV2)
                .where(VerificationResultV2.final_label == lbl)
            )

        true_c = (
            await self._session.execute(_count_label(VerificationLabel.TRUE))
        ).scalar_one()
        false_c = (
            await self._session.execute(_count_label(VerificationLabel.FALSE))
        ).scalar_one()
        partial_c = (
            await self._session.execute(_count_label(VerificationLabel.PARTIALLY_TRUE))
        ).scalar_one()
        nf_c = (
            await self._session.execute(
                _count_label(VerificationLabel.NOT_FOUND_IN_CLAIMED_SOURCE)
            )
        ).scalar_one()

        total_experts = await self._users.count_by_role("expert")
        active_experts_stmt = (
            select(func.count())
            .select_from(User)
            .where(User.role == "expert", User.is_active.is_(True))
        )
        active_experts = (await self._session.execute(active_experts_stmt)).scalar_one()

        from app.features.expert_review.models import ExpertReviewV2

        pending_stmt = (
            select(func.count())
            .select_from(ExpertReviewV2)
            .where(ExpertReviewV2.status == "pending")
        )
        pending = (await self._session.execute(pending_stmt)).scalar_one()

        avg_ms_stmt = select(func.avg(VerificationResultV2.avg_verification_time_ms)).where(
            VerificationResultV2.avg_verification_time_ms.is_not(None)
        )
        avg_ms = (await self._session.execute(avg_ms_stmt)).scalar_one()
        avg_seconds = round(avg_ms / 1000, 2) if avg_ms is not None else None

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
            avg_verification_time_seconds=avg_seconds,
        )

    async def list_credibility_tiers(self) -> list[CredibilityWeightTierResponse]:
        stmt = select(CredibilityWeightTier).order_by(
            CredibilityWeightTier.min_accuracy_pct.asc()
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_tier_to_response(t) for t in rows]

    async def create_credibility_tier(
        self, req: CredibilityWeightTierRequest
    ) -> CredibilityWeightTierResponse:
        tier = CredibilityWeightTier(
            label=req.label,
            min_accuracy_pct=req.min_accuracy_pct,
            max_accuracy_pct=req.max_accuracy_pct,
            weight=req.weight,
            is_active=req.is_active,
        )
        self._session.add(tier)
        await self._session.flush()
        await self._session.refresh(tier)
        logger.info("credibility_tier_created", tier_id=str(tier.id), label=tier.label)
        return _tier_to_response(tier)

    async def update_credibility_tier(
        self, tier_id: uuid.UUID, req: CredibilityWeightTierUpdateRequest
    ) -> CredibilityWeightTierResponse:
        tier = await self._session.get(CredibilityWeightTier, tier_id)
        if tier is None:
            raise RecordNotFoundError(model="CredibilityWeightTier", identifier=str(tier_id))

        updates = req.model_dump(exclude_unset=True)
        for field, value in updates.items():
            setattr(tier, field, value)
        self._session.add(tier)
        await self._session.flush()
        await self._session.refresh(tier)
        return _tier_to_response(tier)

    async def delete_credibility_tier(self, tier_id: uuid.UUID) -> None:
        tier = await self._session.get(CredibilityWeightTier, tier_id)
        if tier is None:
            raise RecordNotFoundError(model="CredibilityWeightTier", identifier=str(tier_id))
        await self._session.delete(tier)
        await self._session.flush()


def _tier_to_response(t: CredibilityWeightTier) -> CredibilityWeightTierResponse:
    return CredibilityWeightTierResponse(
        id=str(t.id),
        label=t.label,
        min_accuracy_pct=t.min_accuracy_pct,
        max_accuracy_pct=t.max_accuracy_pct,
        weight=t.weight,
        is_active=t.is_active,
    )


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
