from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Protocol, runtime_checkable

from app.core.constants import (
    ClaimScope,
    ContentStatus,
    DateStatus,
    ManipulationType,
    PipelineStageID,
    SourceStatus,
)
from app.features.articles.schemas import CandidateArticleSchema, RankedArticleSchema
from app.features.verification.analysis.entities import EntityMention
from app.features.verification.schemas import (
    AnalysisDetails,
    ManipulationFlagsSchema,
    NLIScoresSchema,
    VerificationScoresSchema,
)


@dataclass
class PipelineContext:

    request_id: uuid.UUID = field(default_factory=uuid.uuid4)
    submission_id: uuid.UUID | None = None
    submitter_id: uuid.UUID | None = None
    raw_headline: str = ""
    raw_news_body: str | None = None
    raw_claimed_source: str = ""
    published_date: date | None = None
    force_refresh: bool = False
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
    cached_source_status: SourceStatus | None = None
    cached_content_status: ContentStatus | None = None
    cached_date_status: DateStatus | None = None
    cached_confidence: float | None = None
    cached_reasoning: str | None = None
    cached_scores: VerificationScoresSchema | None = None
    cached_manipulation_flags: ManipulationFlagsSchema | None = None
    cached_matched_articles: list[RankedArticleSchema] = field(default_factory=list)

    search_queries: list[tuple[str, str]] = field(default_factory=list)

    candidate_urls: list[CandidateArticleSchema] = field(default_factory=list)
    search_provider_used: str | None = None

    # Attempted/errored counters for distinguishing "the check ran cleanly
    # and found nothing" (NOT_FOUND) from "the check itself failed" (source
    # status INCOMPLETE) — see s11_classifier.py. A stage records these even
    # though it swallows individual provider/fetch exceptions internally
    # (asyncio.gather(..., return_exceptions=True)) so the pipeline keeps
    # degrading gracefully rather than aborting on one bad provider.
    # Per provider-call outcome accounting (S04). `search_attempted` counts
    # calls that were actually issued or served from cache; unconfigured
    # providers are `search_skipped` and never count as attempts.
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

    extracted_articles: list[RankedArticleSchema] = field(default_factory=list)

    failed_extraction_urls: list[str] = field(default_factory=list)

    ranked_articles: list[RankedArticleSchema] = field(default_factory=list)

    top_article: RankedArticleSchema | None = None

    scores: VerificationScoresSchema = field(default_factory=VerificationScoresSchema)
    claim_entities: list[str] = field(default_factory=list)
    claim_keywords: list[str] = field(default_factory=list)
    claim_numerals: list[str] = field(default_factory=list)
    article_entities: list[str] = field(default_factory=list)
    article_numerals: list[str] = field(default_factory=list)

    claim_entity_types: list[tuple[str, str]] = field(default_factory=list)
    article_entity_types: list[tuple[str, str]] = field(default_factory=list)

    nli_scores: NLIScoresSchema | None = None
    nli_premise: str | None = None

    # Typed entity mentions (S08) kept for the sentence-level checks in S10.
    claim_mentions: list[EntityMention] = field(default_factory=list)
    evidence_mentions: list[EntityMention] = field(default_factory=list)
    ner_available: bool = False

    # Everything persisted in verification_results_v2.analysis_details.
    analysis: AnalysisDetails = field(default_factory=AnalysisDetails)
    # Body comparison diagnostics (HEADLINE_WITH_BODY only).
    body_min_chunk_similarity: float | None = None
    body_complete: bool = True

    manipulation_flags: ManipulationFlagsSchema = field(
        default_factory=ManipulationFlagsSchema
    )
    detected_manipulations: list[ManipulationType] = field(default_factory=list)

    source_status: SourceStatus | None = None
    content_status: ContentStatus | None = None
    date_status: DateStatus | None = None
    confidence: float = 0.0
    reasoning: str = ""

    result_id: uuid.UUID | None = None
    persisted: bool = False

    pipeline_start_time: datetime = field(default_factory=datetime.utcnow)
    stage_timings: dict[str, int] = field(default_factory=dict)

    stage_errors: dict[str, str] = field(default_factory=dict)

    pending_log_entries: list[Any] = field(default_factory=list)

    fatal_error: str | None = None

    @property
    def has_body(self) -> bool:
        return bool(self.normalized_body and len(self.normalized_body.strip()) > 10)

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
    def search_was_incomplete(self) -> bool:
        """True when no evidence was found AND that absence is attributable
        to a failed/inadequate search or failed retrieval rather than an
        adequate search that simply came up empty. S11 reports source_status
        INCOMPLETE (never the confident-negative NOT_FOUND) in that case."""
        if self.has_evidence:
            return False
        return self.retrieval_failed or not bool(self.search_adequate)

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

    def update_scores(self, **kwargs: float | None) -> None:
        current = self.scores.model_dump()
        for key, val in kwargs.items():
            if val is not None:
                current[key] = val
        self.scores = VerificationScoresSchema(**current)


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
    force_refresh: bool = False,
    submission_id: uuid.UUID | None = None,
    submitter_id: uuid.UUID | None = None,
    claim_scope: ClaimScope | None = None,
) -> PipelineContext:
    """Build the pipeline's starting state for one verification run.

    `claim_scope` controls what the pipeline is allowed to treat as "the
    claim" (see `ClaimScope`). When not given explicitly it is inferred from
    whether `news_body` was supplied — the right default for a SOURCE_BASED
    text claim. Photo-card callers must always pass
    `claim_scope=ClaimScope.HEADLINE_ONLY` explicitly and must not pass
    `news_body` — the business rule is that a photo card is verified against
    its headline alone, never a body or caption.
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
        force_refresh=force_refresh,
        claim_scope=resolved_scope,
        pipeline_start_time=datetime.utcnow(),
    )
