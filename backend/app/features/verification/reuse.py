"""Reuse of an earlier identical verification — without sharing submissions.

Verification *work* is reusable; a *submission* is not. A requester always
keeps their own submission row (owner, type, photo-card image, OCR record,
metadata). When an identical, fresh, complete verification exists, its
automated result is copied onto the requester's submission, which is linked to
the original through `duplicate_of_submission_id` /
`verification_results.reused_from_submission_id`.

Expert state is NOT copied: it is read through from the original at display
time (see presenter), so there is one source of truth for review outcomes and
a later finalization of the original is reflected on every copy.

Reusable means: produced by the current pipeline version, no INCOMPLETE
dimension (an incomplete check is never a settled answer), and fresh —
Source NOT_FOUND has a shorter freshness window than a found report. Expert-
finalized results are not subject to the automated freshness window.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import structlog

from app.core.config import get_settings
from app.core.constants import (
    VERIFICATION_PIPELINE_VERSION,
    ContentStatus,
    DateStatus,
    SourceStatus,
    SubmissionStatus,
)
from app.features.submissions.models import Submission
from app.features.submissions.repository import SubmissionRepository
from app.features.verification.models import VerificationResult
from app.features.verification.repository import ResultRepository

logger = structlog.get_logger(__name__)


def freshness_seconds(result: VerificationResult) -> int:
    redis = get_settings().redis
    if result.source_status == SourceStatus.NOT_FOUND:
        return redis.ttl_not_found_result
    return redis.ttl_claim_result


def result_is_reusable(
    result: VerificationResult | None, *, now: datetime | None = None
) -> tuple[bool, str]:
    """(reusable, reason). The reason is logged; it never reaches users."""
    if result is None or result.source_status is None:
        return False, "no_result"
    if result.pipeline_version != VERIFICATION_PIPELINE_VERSION:
        return False, "pipeline_version_mismatch"
    if (
        result.source_status == SourceStatus.INCOMPLETE
        or result.content_status == ContentStatus.INCOMPLETE
        or result.date_status == DateStatus.INCOMPLETE
    ):
        return False, "incomplete_check"
    if result.overall_verdict is not None:  # expert-finalized: durable
        return True, "finalized"
    created = result.created_at
    if created is None:
        return False, "no_timestamp"
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    age = ((now or datetime.now(timezone.utc)) - created).total_seconds()
    if age > freshness_seconds(result):
        return False, "stale"
    return True, "fresh"


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
        """Copy the automated snapshot onto `target` (idempotent)."""
        existing = await self.result_repo.get_by_submission_id(target.id)
        if existing is not None and existing.source_status is not None:
            return existing

        result = await self.result_repo.upsert_result(
            target.id,
            source_status=source_result.source_status,
            content_status=source_result.content_status,
            date_status=source_result.date_status,
            confidence=source_result.confidence or 0.0,
            reasoning=source_result.reasoning or "",
            semantic_similarity=source_result.semantic_similarity,
            entity_match=source_result.entity_match,
            contradiction_score=source_result.contradiction_score,
            keyword_overlap=source_result.keyword_overlap,
            numerical_consistency=source_result.numerical_consistency,
            top_article_id=source_result.top_article_id,
            avg_verification_time_ms=source_result.avg_verification_time_ms,
            manipulation_flags=source_result.manipulation_flags,
            headline_similarity=source_result.headline_similarity,
            body_similarity=source_result.body_similarity,
            passage_similarity=source_result.passage_similarity,
            headline_keyword_coverage=source_result.headline_keyword_coverage,
            passage_keyword_coverage=source_result.passage_keyword_coverage,
            body_keyword_coverage=source_result.body_keyword_coverage,
            claim_scope=source_result.claim_scope,
            pipeline_version=source_result.pipeline_version,
            analysis_details=source_result.analysis_details,
            reused_from_submission_id=source.id,
        )
        target.duplicate_of_submission_id = source.id
        target.status = SubmissionStatus.EXPERT_REVIEW
        target.processing_phase = "DONE"
        await self.submission_repo.session.flush()
        logger.info(
            "result_reused",
            target_submission_id=str(target.id),
            source_submission_id=str(source.id),
        )
        return result
