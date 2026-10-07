from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Protocol, runtime_checkable

from app.core.constants import (
    ClaimScope,
    ContentStatus,
    DateStatus,
    HeadlineCheckStatus,
    PipelineStageID,
    SourceStatus,
)
from app.features.articles.schemas import CandidateArticleSchema, RankedArticleSchema
from app.features.verification.schemas import AnalysisDetails


@dataclass
class PipelineContext:
    """Shared state passed through the verification stages.

    Each decision has its own owner:
      S08 source correspondence  -> source_status, analysis.metrics/search/source_basis
      S09 headline alteration    -> content_status (MATCHED | ALTERED | None),
                                    headline_check_status, analysis.headline_alteration
      S10 body similarity        -> analysis.body_similarity (measurements only)
      S11 date verification      -> date_status, analysis.date
      S12 result assembly        -> confidence, reasoning, analysis bookkeeping
      S13 result persistence     -> result_id, persisted
    """

    request_id: uuid.UUID = field(default_factory=uuid.uuid4)
    submission_id: uuid.UUID | None = None
    submitter_id: uuid.UUID | None = None
    raw_headline: str = ""
    raw_news_body: str | None = None
    raw_claimed_source: str = ""
    published_date: date | None = None
    claim_scope: ClaimScope = ClaimScope.HEADLINE_ONLY

    normalized_headline: str = ""
    normalized_body: str | None = None
    normalized_source: str | None = None
    source_config: dict | None = None
    content_hash: str | None = None

    cache_hit: bool = False
    # The earlier submission whose automated result is being reused (S02).
    # The service layer materialises a result copy for the requester's own
    # submission; the pipeline itself never repoints `submission_id`.
    reused_from_submission_id: uuid.UUID | None = None

    search_queries: list[tuple[str, str]] = field(default_factory=list)
    claim_keywords: list[str] = field(default_factory=list)

    candidate_urls: list[CandidateArticleSchema] = field(default_factory=list)
    search_provider_used: str | None = None

    # Per provider-call outcome accounting (S04), which is what separates
    # "the search ran cleanly and found nothing" (NOT_FOUND) from "the search
    # itself failed" (INCOMPLETE). `search_attempted` counts calls actually
    # issued or served from cache; unconfigured providers are `search_skipped`.
    search_attempted: int = 0
    search_errors: int = 0
    search_success: int = 0
    search_success_empty: int = 0
    search_cached: int = 0
    search_skipped: int = 0
    search_redirect_rejected: int = 0
    search_provider_outcomes: dict[str, dict[str, int]] = field(default_factory=dict)
    search_adequate: bool | None = None
    fetch_attempted: int = 0
    fetch_errors: int = 0
    extraction_attempted: int = 0
    extraction_errors: int = 0

    # S05 -> S06 hand-off: raw HTML of each successfully fetched candidate URL.
    fetched_html: dict[str, str] = field(default_factory=dict)
    extracted_articles: list[RankedArticleSchema] = field(default_factory=list)
    failed_extraction_urls: list[str] = field(default_factory=list)
    ranked_articles: list[RankedArticleSchema] = field(default_factory=list)
    top_article: RankedArticleSchema | None = None

    # Everything persisted in verification_results.analysis_details.
    analysis: AnalysisDetails = field(default_factory=AnalysisDetails)

    source_status: SourceStatus | None = None
    content_status: ContentStatus | None = None
    headline_check_status: HeadlineCheckStatus | None = None
    date_status: DateStatus | None = None
    confidence: float = 0.0
    reasoning: str = ""

    result_id: uuid.UUID | None = None
    persisted: bool = False

    pipeline_start_time: datetime = field(default_factory=datetime.utcnow)
    stage_timings: dict[str, int] = field(default_factory=dict)
    stage_errors: dict[str, str] = field(default_factory=dict)
    fatal_error: str | None = None

    @property
    def has_body(self) -> bool:
        return bool(self.normalized_body and self.normalized_body.strip())

    @property
    def has_evidence(self) -> bool:
        return len(self.ranked_articles) > 0

    @property
    def retrieval_failed(self) -> bool:
        """Candidates existed but every page fetch / extraction failed, so the
        evidence could not be retrieved (as opposed to not existing)."""
        if self.fetch_attempted > 0 and self.fetch_errors >= self.fetch_attempted:
            return True
        if self.extraction_attempted > 0 and self.extraction_errors >= self.extraction_attempted:
            return True
        return False

    @property
    def source_confirmed(self) -> bool:
        return self.source_status == SourceStatus.CONFIRMED and self.top_article is not None

    @property
    def has_fatal_error(self) -> bool:
        return self.fatal_error is not None

    @property
    def elapsed_ms(self) -> int:
        delta = datetime.utcnow() - self.pipeline_start_time
        return int(delta.total_seconds() * 1000)

    @property
    def stage_error_count(self) -> int:
        return len(self.stage_errors)

    def record_stage_error(self, stage_id: PipelineStageID, message: str) -> None:
        self.stage_errors[stage_id.value] = message

    def record_stage_timing(self, stage_id: PipelineStageID, duration_ms: int) -> None:
        self.stage_timings[stage_id.value] = duration_ms


@runtime_checkable
class PipelineStage(Protocol):

    stage_id: PipelineStageID

    async def execute(self, context: PipelineContext) -> PipelineContext: ...


def build_context(
    headline: str,
    claimed_source: str,
    *,
    news_body: str | None = None,
    published_date: date | None = None,
    submission_id: uuid.UUID | None = None,
    submitter_id: uuid.UUID | None = None,
    claim_scope: ClaimScope | None = None,
) -> PipelineContext:
    """Build the pipeline's starting state for one verification run.

    `claim_scope` controls what the pipeline treats as "the claim" (see
    `ClaimScope`). When not given explicitly it is inferred from whether
    `news_body` was supplied - the right default for a SOURCE_BASED text
    claim. Photo-card callers must pass `claim_scope=ClaimScope.HEADLINE_ONLY`
    and no `news_body`: a photo card is verified on its headline alone.
    """
    resolved_scope = claim_scope or (
        ClaimScope.HEADLINE_WITH_BODY
        if news_body and news_body.strip()
        else ClaimScope.HEADLINE_ONLY
    )
    return PipelineContext(
        request_id=uuid.uuid4(),
        submission_id=submission_id,
        submitter_id=submitter_id,
        raw_headline=headline,
        raw_news_body=news_body if resolved_scope == ClaimScope.HEADLINE_WITH_BODY else None,
        raw_claimed_source=claimed_source,
        published_date=published_date,
        claim_scope=resolved_scope,
        pipeline_start_time=datetime.utcnow(),
    )
