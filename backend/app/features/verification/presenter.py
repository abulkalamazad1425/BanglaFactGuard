"""Single read path from the database to `VerificationResponse`.

Every surface that shows a stored result — GET /verify/{id}, GET
/photocard/{id}, the cache-reuse responses — goes through here, so a result
looks the same immediately after verification, after navigating away, after
Redis expiry, and through the database cache fallback. The database row is
authoritative: Redis is never overlaid on it.
"""

from __future__ import annotations

from app.core.constants import (
    ClaimScope,
    HeadlineCheckStatus,
    SearchProvider,
    SourceStatus,
    SubmissionStatus,
    SubmissionType,
)
from app.features.articles.schemas import RankedArticleSchema
from app.features.submissions.models import Submission
from app.features.submissions.repository import RetrievedArticleRepository
from app.features.verification.models import VerificationResult
from app.features.verification.repository import ResultRepository
from app.features.verification.schemas import AnalysisDetails, VerificationResponse


def resolve_scope(submission: Submission, result: VerificationResult) -> ClaimScope:
    """Photo cards are ALWAYS headline-only, whatever an old row says."""
    if submission.submission_type == SubmissionType.PHOTO_CARD:
        return ClaimScope.HEADLINE_ONLY
    if result.claim_scope:
        return ClaimScope(result.claim_scope)
    return (
        ClaimScope.HEADLINE_WITH_BODY
        if submission.body_text and submission.body_text.strip()
        else ClaimScope.HEADLINE_ONLY
    )


async def effective_expert_row(
    submission: Submission,
    result: VerificationResult,
    result_repo: ResultRepository,
) -> VerificationResult:
    """The row whose expert-finalized fields apply to this submission.

    A reused copy reads the original's review outcome live instead of
    snapshotting it, so finalization of the original shows up on every copy.
    """
    if result.reused_from_submission_id:
        original = await result_repo.get_by_submission_id(result.reused_from_submission_id)
        if original is not None and original.overall_verdict is not None:
            return original
    return result


def effective_status(submission: Submission, original_status: SubmissionStatus | None) -> SubmissionStatus:
    if (
        submission.duplicate_of_submission_id
        and original_status == SubmissionStatus.FINALIZED
        and submission.status == SubmissionStatus.EXPERT_REVIEW
    ):
        return SubmissionStatus.FINALIZED
    return submission.status


def is_headline_result(result: VerificationResult) -> bool:
    """True for rows written by the Headline Alteration pipeline. Older rows
    carry a content-level verdict from a different comparison (headline AND
    body, "no conflict -> matched"); it is never relabelled as a headline
    verdict."""
    return result.headline_check_status is not None


def parse_analysis(raw: dict | None) -> AnalysisDetails | None:
    """Validate the stored analysis blob, keeping every section that is still
    valid. A section written in an older shape (e.g. a pre-v4 headline
    detail) is dropped instead of hiding the whole result."""
    if not raw:
        return None
    try:
        return AnalysisDetails.model_validate(raw)
    except Exception:  # noqa: BLE001
        pass
    kept: dict = {}
    for key, value in raw.items():
        if key not in AnalysisDetails.model_fields:
            continue
        try:
            AnalysisDetails.model_validate({key: value})
            kept[key] = value
        except Exception:  # noqa: BLE001
            continue
    try:
        return AnalysisDetails.model_validate(kept)
    except Exception:  # noqa: BLE001
        return None


def _headline_status(result: VerificationResult) -> HeadlineCheckStatus | None:
    try:
        return HeadlineCheckStatus(result.headline_check_status) if result.headline_check_status else None
    except ValueError:
        return None


async def load_verification_response(
    submission: Submission,
    *,
    result_repo: ResultRepository,
    article_repo: RetrievedArticleRepository,
) -> VerificationResponse | None:
    result = await result_repo.get_by_submission_id(submission.id)
    if result is None or result.source_status is None:
        return None

    scope = resolve_scope(submission, result)
    expert = await effective_expert_row(submission, result, result_repo)
    is_finalized = expert.overall_verdict is not None
    current = is_headline_result(result)

    ai_source = result.source_status or SourceStatus.INCOMPLETE
    ai_headline = result.content_status if current else None
    displayed_source = (expert.final_source_status if is_finalized else None) or ai_source
    displayed_content = expert.final_content_status if is_finalized else ai_headline
    displayed_date = expert.final_date_status if is_finalized else result.date_status
    was_overridden = is_finalized and (
        (expert.final_source_status is not None and expert.final_source_status != ai_source)
        or (expert.final_content_status is not None and expert.final_content_status != ai_headline)
        or (expert.final_date_status is not None and expert.final_date_status != result.date_status)
    )

    origin_id = result.reused_from_submission_id or submission.id
    articles = await article_repo.get_for_submission(
        origin_id, successful_only=True, order_by_rank=True, limit=3
    )
    # The source S08 selected comes first even when it was not rank #1.
    articles = sorted(articles, key=lambda a: a.id != result.top_article_id)

    analysis = parse_analysis(result.analysis_details)
    if analysis is not None and not current:
        analysis.headline_alteration = None

    return VerificationResponse(
        submission_id=submission.id,
        # Expert-finalized only. The automated system never computes this.
        overall_verdict=expert.overall_verdict if is_finalized else None,
        is_finalized=is_finalized,
        review_pending=not is_finalized,
        was_overridden=was_overridden,
        ai_source_status=ai_source,
        ai_content_status=ai_headline,
        ai_date_status=result.date_status,
        source_status=displayed_source,
        content_status=displayed_content,
        headline_check_status=_headline_status(result),
        date_status=displayed_date,
        confidence=result.confidence or 0.0,
        reasoning=result.reasoning or "",
        matched_articles=[
            RankedArticleSchema(
                url=a.url,
                title=a.title,
                author=a.author,
                published_date=a.published_date,
                body=a.body,
                rank_score=a.rank_score or 0.0,
                search_provider=SearchProvider.INTERNAL_SITE,
                extraction_method=a.extraction_method,
            )
            for a in articles
        ],
        normalized_source=submission.claimed_source_text,
        cached=result.reused_from_submission_id is not None,
        processing_time_ms=result.avg_verification_time_ms,
        created_at=result.created_at,
        claim_scope=scope,
        pipeline_version=result.pipeline_version,
        legacy_result=not current,
        analysis=analysis,
    )
