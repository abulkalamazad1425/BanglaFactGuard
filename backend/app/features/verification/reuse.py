from __future__ import annotations

import uuid
from datetime import datetime

import structlog

from app.core.constants import (
    VERIFICATION_PIPELINE_VERSION,
    BodyComparisonStatus,
    DateStatus,
    HeadlineCheckStatus,
    JobPhase,
    SourceStatus,
    SubmissionStatus,
)
from app.features.submissions.models import Submission
from app.features.submissions.repository import SubmissionRepository
from app.features.verification.models import VerificationResult
from app.features.verification.repository import ResultRepository

logger = structlog.get_logger(__name__)


REUSED_FROM_KEY = "reused_from_submission_id"


def result_is_reusable(
    result: VerificationResult | None, *, now: datetime | None = None
) -> tuple[bool, str]:
    if result is None or result.source_status is None:
        return False, "no_result"
    if result.pipeline_version != VERIFICATION_PIPELINE_VERSION:
        return False, "pipeline_version_mismatch"
    if result.reused_from_submission_id is not None or (result.analysis_details or {}).get(REUSED_FROM_KEY):
        return False, "copied_result"
    if result.source_status == SourceStatus.INCOMPLETE or result.date_status == DateStatus.INCOMPLETE:
        return False, "incomplete_check"
    if result.source_status == SourceStatus.CONFIRMED and (
        result.content_status is None or result.headline_check_status != HeadlineCheckStatus.COMPLETED.value
    ):
        return False, "no_headline_verdict"
    if (
        result.source_status == SourceStatus.CONFIRMED
        and result.body_comparison_status == BodyComparisonStatus.UNAVAILABLE.value
    ):
        return False, "body_scores_unavailable"
    return True, "reusable"


class ResultReuseService:
    def __init__(
        self, submission_repo: SubmissionRepository, result_repo: ResultRepository
    ) -> None:
        self.submission_repo = submission_repo
        self.result_repo = result_repo

    async def find_reusable(
        self, content_hash: str, *, exclude_submission_id: uuid.UUID | None = None
    ) -> tuple[Submission, VerificationResult] | None:
        for candidate in await self.submission_repo.get_reusable_candidates(content_hash):
            if exclude_submission_id and candidate.id == exclude_submission_id:
                continue
            result = await self.result_repo.get_by_submission_id(candidate.id)
            ok, reason = result_is_reusable(result)
            if ok:
                return candidate, result  # type: ignore[return-value]
            logger.debug("reuse_candidate_rejected", submission_id=str(candidate.id), reason=reason)
        return None

    async def materialize(
        self,
        *,
        source: Submission,
        source_result: VerificationResult,
        target: Submission,
    ) -> VerificationResult:
        existing = await self.result_repo.get_by_submission_id(target.id)
        if existing is not None and existing.source_status is not None:
            return existing

        result = await self.result_repo.upsert_result(
            target.id,
            source_status=source_result.source_status,
            content_status=source_result.content_status,
            headline_check_status=source_result.headline_check_status,
            headline_exact_match=source_result.headline_exact_match,
            body_comparison_status=source_result.body_comparison_status,
            date_status=source_result.date_status,
            confidence=source_result.confidence or 0.0,
            reasoning=source_result.reasoning or "",
            headline_similarity=source_result.headline_similarity,
            headline_keyword_coverage=source_result.headline_keyword_coverage,
            passage_keyword_coverage=source_result.passage_keyword_coverage,
            top_article_id=source_result.top_article_id,
            avg_verification_time_ms=source_result.avg_verification_time_ms,
            claim_scope=source_result.claim_scope,
            pipeline_version=source_result.pipeline_version,
            analysis_details={
                **{k: v for k, v in (source_result.analysis_details or {}).items() if k != "timings"},
                REUSED_FROM_KEY: str(source.id),
            },
            reused_from_submission_id=source.id,
        )
        target.duplicate_of_submission_id = source.id
        target.status = SubmissionStatus.EXPERT_REVIEW
        target.processing_phase = JobPhase.DONE.value
        await self.submission_repo.session.flush()
        logger.info(
            "result_reused",
            target_submission_id=str(target.id),
            source_submission_id=str(source.id),
        )
        return result
