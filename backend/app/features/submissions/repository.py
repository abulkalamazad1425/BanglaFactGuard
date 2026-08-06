from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import SubmissionStatus, SubmissionType, VerificationLabel
from app.features.submissions.models import (
    OcrExtraction,
    RetrievedArticleV2,
    SourceEvidenceQuery,
    Submission,
)
from app.shared.base_repository import BaseRepository

_VERIFIED_STATUSES = (SubmissionStatus.EXPERT_REVIEW, SubmissionStatus.FINALIZED)


class SubmissionRepository(BaseRepository[Submission]):

    model_class = Submission

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_by_content_hash(self, content_hash: str) -> Submission | None:
        stmt = (
            select(Submission).where(Submission.content_hash == content_hash).limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

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
        await self.set_status(submission_id, SubmissionStatus.EXPERT_REVIEW)

    async def mark_finalized(self, submission_id: uuid.UUID) -> None:
        await self.set_status(submission_id, SubmissionStatus.FINALIZED)

    async def mark_failed(self, submission_id: uuid.UUID) -> None:
        await self.set_status(submission_id, SubmissionStatus.FAILED)

    async def get_recent(
        self,
        *,
        status: SubmissionStatus | None = SubmissionStatus.EXPERT_REVIEW,
        submission_type: SubmissionType | None = None,
        limit: int = 20,
    ) -> list[Submission]:
        stmt = select(Submission)
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
        verdict: VerificationLabel | None = None,
        method: SubmissionType | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        source_id: uuid.UUID | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Submission], int]:
        """Fact Explorer search — browse verified (EXPERT_REVIEW/FINALIZED)
        submissions with optional filters. Returns (rows, total_count)."""
        from sqlalchemy import func

        from app.features.verification.models import VerificationResultV2

        conditions = [Submission.status.in_(_VERIFIED_STATUSES)]

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

        if verdict is not None:
            base = base.join(
                VerificationResultV2,
                VerificationResultV2.submission_id == Submission.id,
            )
            count_base = count_base.join(
                VerificationResultV2,
                VerificationResultV2.submission_id == Submission.id,
            )
            conditions.append(VerificationResultV2.final_label == verdict)

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
