from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Protocol, runtime_checkable

from app.core.constants import (
    ManipulationType,
    PipelineStageID,
    VerificationLabel,
)
from app.features.articles.schemas import CandidateArticleSchema, RankedArticleSchema
from app.features.verification.schemas import (
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

    normalized_headline: str = ""
    normalized_body: str | None = None
    normalized_source: str | None = None
    source_config: dict | None = None
    content_hash: str | None = None

    cache_hit: bool = False
    cached_label: VerificationLabel | None = None
    cached_confidence: float | None = None
    cached_reasoning: str | None = None
    cached_scores: VerificationScoresSchema | None = None
    cached_manipulation_flags: ManipulationFlagsSchema | None = None
    cached_matched_articles: list[RankedArticleSchema] = field(default_factory=list)

    search_queries: list[tuple[str, str]] = field(default_factory=list)

    candidate_urls: list[CandidateArticleSchema] = field(default_factory=list)
    search_provider_used: str | None = None

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

    manipulation_flags: ManipulationFlagsSchema = field(
        default_factory=ManipulationFlagsSchema
    )
    detected_manipulations: list[ManipulationType] = field(default_factory=list)

    label: VerificationLabel | None = None
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
) -> PipelineContext:
    return PipelineContext(
        request_id=uuid.uuid4(),
        submission_id=submission_id,
        submitter_id=submitter_id,
        raw_headline=headline,
        raw_news_body=news_body,
        raw_claimed_source=claimed_source,
        published_date=published_date,
        force_refresh=force_refresh,
        pipeline_start_time=datetime.utcnow(),
    )
