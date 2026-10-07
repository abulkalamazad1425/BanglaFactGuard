from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import SubmissionStatus
from app.core.exceptions import (
    DomainValidationError,
    DuplicateRecordError,
    RecordNotFoundError,
    WeakPasswordError,
)
from app.features.admin.schemas import (
    AdminDashboardResponse,
    AdminStatsResponse,
    CreateExpertRequest,
    CredibilityWeightTierRequest,
    CredibilityWeightTierResponse,
    CredibilityWeightTierUpdateRequest,
    ExpertResponse,
    ResetExpertPasswordRequest,
    UpdateExpertRequest,
    VotingConfigResponse,
    VotingConfigUpdateRequest,
)
from app.features.auth.models import User
from app.features.auth.repository import RefreshTokenRepository, UserRepository
from app.features.auth.security import hash_password
from app.features.expert_review.models import CredibilityWeightTier, VotingConfig
from app.features.expert_review.repository import (
    CredibilityWeightTierRepository,
    ExpertProfileRepository,
    VotingConfigRepository,
)
from app.features.submissions.models import Submission
from app.features.verification.models import VerificationResult

logger = structlog.get_logger(__name__)


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
        )
        user = await self._users.create(user)

        profile = await self._profiles.get_or_create(
            user.id,
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

        async def count(*conditions) -> int:
            stmt = select(func.count()).select_from(Submission).where(*conditions)
            return (await self._session.execute(stmt)).scalar_one()

        original = Submission.duplicate_of_submission_id.is_(None)
        active_experts = (
            await self._session.execute(
                select(func.count()).select_from(User).where(User.role == "expert", User.is_active.is_(True))
            )
        ).scalar_one()
        avg_ms = (
            await self._session.execute(
                select(func.avg(VerificationResult.avg_verification_time_ms)).where(
                    VerificationResult.avg_verification_time_ms.is_not(None)
                )
            )
        ).scalar_one()

        return AdminStatsResponse(
            total_submissions=await count(),
            submissions_last_30_days=await count(Submission.created_at >= thirty_days_ago),
            # Claims open for expert voting (previously a count of vote rows).
            pending_expert_reviews=await count(Submission.status == SubmissionStatus.EXPERT_REVIEW, original),
            escalated_claims=await count(Submission.status == SubmissionStatus.ESCALATED, original),
            total_experts=await self._users.count_by_role("expert"),
            active_experts=active_experts,
            avg_verification_time_seconds=round(avg_ms / 1000, 2) if avg_ms is not None else None,
        )

    async def get_dashboard(self) -> AdminDashboardResponse:
        from app.features.admin.dashboard import build_admin_dashboard

        return await build_admin_dashboard(self._session)

    async def list_credibility_tiers(self) -> list[CredibilityWeightTierResponse]:
        stmt = select(CredibilityWeightTier).order_by(
            CredibilityWeightTier.min_accuracy_pct.asc()
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_tier_to_response(t) for t in rows]

    async def _validate_tier(
        self,
        *,
        tier_id: uuid.UUID | None,
        min_pct: float,
        max_pct: float,
        weight: float,
        is_active: bool,
    ) -> None:
        if max_pct <= min_pct:
            raise DomainValidationError(
                message="max_accuracy_pct must be greater than min_accuracy_pct."
            )

        if not is_active:
            return  # inactive tiers don't participate in the 0-100 tiling

        stmt = select(CredibilityWeightTier).where(CredibilityWeightTier.is_active.is_(True))
        if tier_id is not None:
            stmt = stmt.where(CredibilityWeightTier.id != tier_id)
        others = (await self._session.execute(stmt)).scalars().all()
        ranges = sorted(
            [(t.min_accuracy_pct, t.max_accuracy_pct) for t in others] + [(min_pct, max_pct)],
            key=lambda r: r[0],
        )
        if ranges[0][0] != 0.0:
            raise DomainValidationError(
                message=f"Active tiers must start at 0% (currently starts at {ranges[0][0]}%)."
            )
        for (_, hi1), (lo2, _) in zip(ranges, ranges[1:]):
            if hi1 > lo2:
                raise DomainValidationError(message=f"Tier ranges overlap around {lo2}%.")
            if hi1 < lo2:
                raise DomainValidationError(
                    message=f"Gap between tiers from {hi1}% to {lo2}% — every accuracy% must be covered."
                )
        if ranges[-1][1] != 100.0:
            raise DomainValidationError(
                message=f"Active tiers must end at 100% (currently ends at {ranges[-1][1]}%)."
            )

    async def create_credibility_tier(
        self, req: CredibilityWeightTierRequest, admin_id: uuid.UUID | None = None
    ) -> CredibilityWeightTierResponse:
        await self._validate_tier(
            tier_id=None,
            min_pct=req.min_accuracy_pct,
            max_pct=req.max_accuracy_pct,
            weight=req.weight,
            is_active=req.is_active,
        )
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
        self,
        tier_id: uuid.UUID,
        req: CredibilityWeightTierUpdateRequest,
        admin_id: uuid.UUID | None = None,
    ) -> CredibilityWeightTierResponse:
        tier = await self._session.get(CredibilityWeightTier, tier_id)
        if tier is None:
            raise RecordNotFoundError(model="CredibilityWeightTier", identifier=str(tier_id))

        updates = req.model_dump(exclude_unset=True)
        await self._validate_tier(
            tier_id=tier_id,
            min_pct=updates.get("min_accuracy_pct", tier.min_accuracy_pct),
            max_pct=updates.get("max_accuracy_pct", tier.max_accuracy_pct),
            weight=updates.get("weight", tier.weight),
            is_active=updates.get("is_active", tier.is_active),
        )
        for field, value in updates.items():
            setattr(tier, field, value)
        self._session.add(tier)
        await self._session.flush()
        await self._session.refresh(tier)
        return _tier_to_response(tier)

    async def delete_credibility_tier(
        self, tier_id: uuid.UUID, admin_id: uuid.UUID | None = None
    ) -> None:
        tier = await self._session.get(CredibilityWeightTier, tier_id)
        if tier is None:
            raise RecordNotFoundError(model="CredibilityWeightTier", identifier=str(tier_id))
        await self._session.delete(tier)
        await self._session.flush()

    async def get_voting_config(self) -> VotingConfigResponse:
        row = await VotingConfigRepository(self._session).get_or_create()
        return _voting_config_to_response(row)

    async def update_voting_config(
        self, req: VotingConfigUpdateRequest, admin_id: uuid.UUID | None = None
    ) -> VotingConfigResponse:
        repo = VotingConfigRepository(self._session)
        row = await repo.get_or_create()
        updates = req.model_dump(exclude_unset=True)
        row = await repo.update(row, **updates)
        if "activation_threshold_votes" in updates:
            from sqlalchemy import case, update
            from app.features.expert_review.models import ExpertProfile
            await self._session.execute(update(ExpertProfile).values(credibility_score=case(
                ((ExpertProfile.total_votes > 0) & (ExpertProfile.total_votes >= row.activation_threshold_votes),
                 ExpertProfile.correct_votes * 1.0 / func.nullif(ExpertProfile.total_votes, 0)),
                else_=None,
            )))
        logger.info("voting_config_updated", **updates)
        return _voting_config_to_response(row)



def _voting_config_to_response(row: VotingConfig) -> VotingConfigResponse:
    return VotingConfigResponse(
        id=str(row.id),
        min_expert_votes=row.min_expert_votes,
        activation_threshold_votes=row.activation_threshold_votes,
        verified_threshold=row.verified_threshold,
        lead_margin=row.lead_margin,
        max_review_votes=row.max_review_votes,
        max_review_hours=row.max_review_hours,
        updated_at=row.updated_at,
    )


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
