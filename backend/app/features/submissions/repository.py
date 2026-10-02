from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import (
    ContentStatus,
    DateStatus,
    OverallVerdict,
    SourceStatus,
    SubmissionStatus,
    SubmissionType,
)
from app.features.submissions.models import (
    OcrExtraction,
    RetrievedArticleV2,
    SourceEvidenceQuery,
    Submission,
)
from app.shared.base_repository import BaseRepository

_VERIFIED_STATUSES = (SubmissionStatus.EXPERT_REVIEW, SubmissionStatus.FINALIZED)
_IN_FLIGHT_STATUSES = (SubmissionStatus.PENDING, SubmissionStatus.PROCESSING)


class SubmissionRepository(BaseRepository[Submission]):

    model_class = Submission

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_by_id_locked(self, submission_id: uuid.UUID) -> Submission:
        """Row-locks the submission for the rest of this transaction —
        concurrent vote/finalize attempts on the same claim serialize on
        this lock instead of racing, since a single request's session is
        one transaction (committed when the request completes)."""
        from app.core.exceptions import RecordNotFoundError

        stmt = select(Submission).where(Submission.id == submission_id).with_for_update()
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            raise RecordNotFoundError(model="Submission", identifier=str(submission_id))
        return row

    async def get_by_content_hash(self, content_hash: str) -> Submission | None:
        stmt = (
            select(Submission).where(Submission.content_hash == content_hash).limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_reusable_candidates(
        self, content_hash: str, *, limit: int = 5
    ) -> list[Submission]:
        """Verified, non-duplicate submissions with this exact claim identity,
        newest first. Callers still validate each one's result for
        reusability and freshness."""
        stmt = (
            select(Submission)
            .where(
                and_(
                    Submission.content_hash == content_hash,
                    Submission.status.in_(_VERIFIED_STATUSES),
                    Submission.duplicate_of_submission_id.is_(None),
                )
            )
            .order_by(Submission.created_at.desc())
            .limit(limit)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def get_verified_by_content_hash(
        self, content_hash: str
    ) -> Submission | None:
        stmt = (
            select(Submission)
            .where(
                and_(
                    Submission.content_hash == content_hash,
                    Submission.status.in_(_VERIFIED_STATUSES),
                )
            )
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_in_flight_by_content_hash(
        self, content_hash: str
    ) -> Submission | None:
        """A submission for this claim that is queued or still running."""
        stmt = (
            select(Submission)
            .where(
                and_(
                    Submission.content_hash == content_hash,
                    Submission.status.in_(_IN_FLIGHT_STATUSES),
                )
            )
            .order_by(Submission.created_at.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def set_status(
        self, submission_id: uuid.UUID, status: SubmissionStatus
    ) -> None:
        from sqlalchemy import update

        stmt = (
            update(Submission)
            .where(Submission.id == submission_id)
            .values(status=status)
        )
        await self.session.execute(stmt)
        await self.session.flush()

    async def mark_processing(self, submission_id: uuid.UUID) -> None:
        await self.set_status(submission_id, SubmissionStatus.PROCESSING)

    async def mark_ai_done(self, submission_id: uuid.UUID) -> None:
        from sqlalchemy import update

        # Also clears any failure left by an earlier, retried attempt.
        await self.session.execute(
            update(Submission)
            .where(Submission.id == submission_id)
            .values(
                status=SubmissionStatus.EXPERT_REVIEW,
                processing_phase="DONE",
                failure_reason=None,
            )
        )
        await self.session.flush()

    async def mark_finalized(self, submission_id: uuid.UUID) -> None:
        await self.set_status(submission_id, SubmissionStatus.FINALIZED)

    async def mark_failed(
        self, submission_id: uuid.UUID, reason: str | None = None
    ) -> bool:
        """Terminal failure. Returns True only on the transition INTO failed,
        so callers can emit the failure notification exactly once."""
        from sqlalchemy import update

        stmt = (
            update(Submission)
            .where(
                Submission.id == submission_id,
                Submission.status.notin_(
                    (SubmissionStatus.FAILED, SubmissionStatus.FINALIZED, SubmissionStatus.ESCALATED)
                ),
            )
            .values(
                status=SubmissionStatus.FAILED,
                processing_phase="FAILED",
                failure_reason=(reason or "Verification could not be completed.")[:2000],
            )
        )
        res = await self.session.execute(stmt)
        await self.session.flush()
        return bool(res.rowcount)

    async def set_phase(self, submission_id: uuid.UUID, phase: str) -> None:
        from sqlalchemy import update

        await self.session.execute(
            update(Submission).where(Submission.id == submission_id).values(processing_phase=phase)
        )
        await self.session.flush()

    async def get_recent(
        self,
        *,
        status: SubmissionStatus | None = SubmissionStatus.EXPERT_REVIEW,
        submission_type: SubmissionType | None = None,
        limit: int = 20,
        include_duplicates: bool = False,
    ) -> list[Submission]:
        stmt = select(Submission)
        if not include_duplicates:
            # A duplicate is a requester's own copy of an already-reviewed
            # claim; experts review (and the explorer lists) the original.
            stmt = stmt.where(Submission.duplicate_of_submission_id.is_(None))
        if status is not None:
            stmt = stmt.where(Submission.status == status)
        if submission_type is not None:
            stmt = stmt.where(Submission.submission_type == submission_type)
        stmt = stmt.order_by(Submission.created_at.desc()).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_date_range(
        self,
        start_date: date,
        end_date: date,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Submission]:
        stmt = (
            select(Submission)
            .where(
                and_(
                    Submission.published_date >= start_date,
                    Submission.published_date <= end_date,
                )
            )
            .order_by(Submission.published_date.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def search(
        self,
        *,
        keyword: str | None = None,
        source_status: SourceStatus | None = None,
        content_status: ContentStatus | None = None,
        date_status: DateStatus | None = None,
        overall_verdict: OverallVerdict | None = None,
        method: SubmissionType | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        source_id: uuid.UUID | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Submission], int]:
        """Fact Explorer search — browse verified (EXPERT_REVIEW/FINALIZED)
        submissions with optional filters. Returns (rows, total_count).

        overall_verdict spans every submission type (its finalized value
        lives on VerificationResultV2 for SOURCE_BASED/PHOTO_CARD, and on
        MultimodalAnalysis for MULTIMODAL) and only matches claims that have
        actually been expert-finalized — a claim still under review doesn't
        match any overall_verdict filter, even though its AI-implied value
        may be shown on its own detail page.
        """
        from sqlalchemy import func

        from app.features.multimodal.models import MultimodalAnalysis
        from app.features.verification.models import VerificationResultV2

        conditions = [
            Submission.status.in_(_VERIFIED_STATUSES),
            Submission.duplicate_of_submission_id.is_(None),
        ]

        if keyword:
            like = f"%{keyword}%"
            conditions.append(
                or_(Submission.headline.ilike(like), Submission.body_text.ilike(like))
            )
        if method is not None:
            conditions.append(Submission.submission_type == method)
        if date_from is not None:
            conditions.append(Submission.created_at >= date_from)
        if date_to is not None:
            conditions.append(Submission.created_at <= date_to)
        if source_id is not None:
            conditions.append(Submission.claimed_source_id == source_id)

        base = select(Submission)
        count_base = select(func.count(func.distinct(Submission.id)))

        needs_result_join = (
            source_status is not None
            or content_status is not None
            or date_status is not None
        )
        joined_result = False

        if needs_result_join:
            base = base.join(
                VerificationResultV2,
                VerificationResultV2.submission_id == Submission.id,
            )
            count_base = count_base.join(
                VerificationResultV2,
                VerificationResultV2.submission_id == Submission.id,
            )
            joined_result = True
            if source_status is not None:
                conditions.append(VerificationResultV2.source_status == source_status)
            if content_status is not None:
                conditions.append(VerificationResultV2.content_status == content_status)
            if date_status is not None:
                conditions.append(VerificationResultV2.date_status == date_status)

        if overall_verdict is not None:
            if not joined_result:
                base = base.outerjoin(
                    VerificationResultV2,
                    VerificationResultV2.submission_id == Submission.id,
                )
                count_base = count_base.outerjoin(
                    VerificationResultV2,
                    VerificationResultV2.submission_id == Submission.id,
                )
            base = base.outerjoin(
                MultimodalAnalysis,
                MultimodalAnalysis.submission_id == Submission.id,
            )
            count_base = count_base.outerjoin(
                MultimodalAnalysis,
                MultimodalAnalysis.submission_id == Submission.id,
            )
            conditions.append(
                or_(
                    VerificationResultV2.overall_verdict == overall_verdict,
                    MultimodalAnalysis.expert_overall_verdict == overall_verdict,
                )
            )

        stmt = (
            base.where(and_(*conditions))
            .order_by(Submission.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        count_stmt = count_base.where(and_(*conditions))

        rows = list((await self.session.execute(stmt)).scalars().all())
        total = (await self.session.execute(count_stmt)).scalar_one()
        return rows, total


class SourceEvidenceQueryRepository(BaseRepository[SourceEvidenceQuery]):

    model_class = SourceEvidenceQuery

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_for_submission(
        self, submission_id: uuid.UUID
    ) -> list[SourceEvidenceQuery]:
        stmt = select(SourceEvidenceQuery).where(
            SourceEvidenceQuery.submission_id == submission_id
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


class RetrievedArticleV2Repository(BaseRepository[RetrievedArticleV2]):

    model_class = RetrievedArticleV2

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_by_url_hash(
        self, submission_id: uuid.UUID, url_hash: str
    ) -> RetrievedArticleV2 | None:
        stmt = (
            select(RetrievedArticleV2)
            .where(
                and_(
                    RetrievedArticleV2.submission_id == submission_id,
                    RetrievedArticleV2.url_hash == url_hash,
                )
            )
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_for_submission(
        self,
        submission_id: uuid.UUID,
        *,
        successful_only: bool = True,
        order_by_rank: bool = True,
        limit: int = 10,
    ) -> list[RetrievedArticleV2]:
        conditions = [RetrievedArticleV2.submission_id == submission_id]
        if successful_only:
            conditions.append(RetrievedArticleV2.extraction_success.is_(True))

        stmt = select(RetrievedArticleV2).where(and_(*conditions))
        if order_by_rank:
            stmt = stmt.order_by(RetrievedArticleV2.rank_score.desc().nullslast())
        stmt = stmt.limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_top_ranked(
        self, submission_id: uuid.UUID
    ) -> RetrievedArticleV2 | None:
        stmt = (
            select(RetrievedArticleV2)
            .where(
                and_(
                    RetrievedArticleV2.submission_id == submission_id,
                    RetrievedArticleV2.extraction_success.is_(True),
                )
            )
            .order_by(RetrievedArticleV2.rank_score.desc().nullslast())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def count_for_submission(
        self, submission_id: uuid.UUID, *, successful_only: bool = False
    ) -> int:
        from sqlalchemy import func

        conditions = [RetrievedArticleV2.submission_id == submission_id]
        if successful_only:
            conditions.append(RetrievedArticleV2.extraction_success.is_(True))
        stmt = (
            select(func.count())
            .select_from(RetrievedArticleV2)
            .where(and_(*conditions))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def update_rank_score(
        self, article_id: uuid.UUID, rank_score: float
    ) -> None:
        from sqlalchemy import update

        stmt = (
            update(RetrievedArticleV2)
            .where(RetrievedArticleV2.id == article_id)
            .values(rank_score=rank_score)
        )
        await self.session.execute(stmt)
        await self.session.flush()


class OcrExtractionRepository(BaseRepository[OcrExtraction]):

    model_class = OcrExtraction

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_by_submission_id(
        self, submission_id: uuid.UUID
    ) -> OcrExtraction | None:
        stmt = (
            select(OcrExtraction)
            .where(OcrExtraction.submission_id == submission_id)
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
