"""
app/pipelines/context.py
=========================
PipelineContext dataclass and PipelineStage Protocol — the two foundational
contracts that all 12 pipeline stages are built around.

## Design rationale

### Why a shared mutable context?

Each stage in the pipeline needs access to data produced by earlier stages.
The alternatives were:

1. **Return-value chaining**: Stage N returns a value → Stage N+1 receives it
   as an argument. Brittle: every stage must know the complete signature of the
   stage before it.

2. **Shared mutable context** (chosen): A single `PipelineContext` object is
   passed through every stage. Each stage reads what it needs from the context
   and writes its output back into it. Stages are fully decoupled — they only
   know the context contract, not each other.

3. **Event bus**: Overcomplicated for a linear 12-stage pipeline.

### Why a `Protocol` for stages?

Using `typing.Protocol` instead of an abstract base class:
- Stages satisfy the protocol structurally (duck typing) — no inheritance
  required, so they can be instantiated and tested completely independently.
- The orchestrator can accept any object that has the right shape — useful
  for inserting test doubles or mocked stages in integration tests.

### Context field conventions

- Fields that are None at the start become populated as stages progress.
- `stage_errors` accumulates non-fatal stage failures; the orchestrator
  uses this to decide final confidence and labels.
- `cache_hit` being True causes the orchestrator to short-circuit after
  Stage 2 — stages 3–12 are skipped.
- `stage_timings` maps each PipelineStageID to its wall-clock ms —
  persisted in Stage 12 as `duration_ms` in VerificationLog.
- `pending_log_entries` is a list of VerificationLog instances built up
  throughout the pipeline and flushed to the DB in Stage 12 as a batch.
"""

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
from app.features.verification.schemas import ManipulationFlagsSchema, NLIScoresSchema, VerificationScoresSchema


# ---------------------------------------------------------------------------
# PipelineContext
# ---------------------------------------------------------------------------


@dataclass
class PipelineContext:
    """
    Mutable context object shared across all 12 pipeline stages.

    Created once at the start of a verification request and passed through
    every stage sequentially. Each stage reads inputs it needs and writes
    its outputs back into designated fields.

    The orchestrator inspects `cache_hit`, `stage_errors`, and the verdict
    fields after all stages complete to assemble the final response.

    ## Input fields (populated before pipeline starts)

    Attributes:
        request_id:          UUID of the HTTP request (for log correlation).
        claim_id:            UUID of the verified_claims record (set in Stage 12
                             after DB insert, or pre-set if re-verifying).
        raw_headline:        Headline as received from the API request.
        raw_news_body:       News body as received (may be None).
        raw_claimed_source:  Claimed source as received from the API request.
        published_date:      Optional date from the request.
        force_refresh:       Whether to bypass cached results.

    ## Stage 1 outputs (normalization)

        normalized_headline:       Unicode/Bangla-normalized headline.
        normalized_body:           Unicode/Bangla-normalized body (may be None).
        normalized_source:         Resolved canonical domain (e.g. "prothomalo.com").
        claim_hash:                SHA-256 of (normalized_headline + normalized_source).

    ## Stage 2 outputs (cache lookup)

        cache_hit:                 True → cached result found, skip Stages 3–12.
        cached_label:              Label from cache (set only if cache_hit=True).
        cached_confidence:         Confidence from cache.
        cached_reasoning:          Reasoning string from cache.
        cached_scores:             Score breakdown from cache.

    ## Stage 3 outputs (query generation)

        search_queries:            List of (query_text, query_type) tuples.

    ## Stage 4 outputs (source-constrained search)

        candidate_urls:            Deduplicated list of CandidateArticleSchema.

    ## Stage 5 outputs (evidence retrieval)
        (Stage 5 triggers async fetching of candidate_urls — stored in Stage 6)

    ## Stage 6 outputs (article extraction)

        ranked_articles:           Articles after extraction (pre-ranking).
                                   Populated here as ExtractedContentSchema-equivalent
                                   within RankedArticleSchema (rank_score=0.0 initially).

    ## Stage 7 outputs (evidence ranking)

        ranked_articles:           Same list, now with rank_score populated.

    ## Stage 8 outputs (similarity analysis)

        scores:                    VerificationScoresSchema (partial — NLI score added in S9).
        claim_entities:            Entities extracted from the claim headline/body.
        claim_keywords:            Keywords extracted from the claim.
        claim_numerals:            Numerals extracted from the claim.

    ## Stage 9 outputs (contradiction detection)

        nli_scores:                Raw NLI triple for the best-matching article.
        scores.contradiction_score: Updated in-place on the scores object.

    ## Stage 10 outputs (manipulation detection)

        manipulation_flags:        ManipulationFlagsSchema with boolean detections.
        detected_manipulations:    List of ManipulationType enums (for detailed reasoning).

    ## Stage 11 outputs (classification)

        label:                     Final VerificationLabel verdict.
        confidence:                Overall confidence score [0, 1].
        reasoning:                 Human-readable reasoning string.

    ## Stage 12 outputs (persistence)

        claim_id:                  Set/confirmed after DB write.
        result_id:                 UUID of the VerificationResult DB record.

    ## Pipeline metadata

        pipeline_start_time:       datetime.utcnow() when the pipeline started.
        stage_timings:             Maps PipelineStageID → wall-clock ms.
        stage_errors:              Maps PipelineStageID → error message (non-fatal).
        pending_log_entries:       VerificationLog instances built during the run,
                                   flushed to DB in Stage 12.
        fatal_error:               Set by the orchestrator if an unrecoverable
                                   exception is raised (pipeline is aborted).
    """

    # -----------------------------------------------------------------------
    # Input fields
    # -----------------------------------------------------------------------
    request_id: uuid.UUID = field(default_factory=uuid.uuid4)
    claim_id: uuid.UUID | None = None
    raw_headline: str = ""
    raw_news_body: str | None = None
    raw_claimed_source: str = ""
    published_date: date | None = None
    force_refresh: bool = False

    # -----------------------------------------------------------------------
    # Stage 1 — Normalization
    # -----------------------------------------------------------------------
    normalized_headline: str = ""
    normalized_body: str | None = None
    normalized_source: str | None = None  # canonical domain, e.g. "prothomalo.com"
    source_config: dict | None = None  # Scraping config from verified_sources DB
    claim_hash: str | None = None

    # -----------------------------------------------------------------------
    # Stage 2 — Cache Lookup
    # -----------------------------------------------------------------------
    cache_hit: bool = False
    cached_label: VerificationLabel | None = None
    cached_confidence: float | None = None
    cached_reasoning: str | None = None
    cached_scores: VerificationScoresSchema | None = None
    cached_manipulation_flags: ManipulationFlagsSchema | None = None
    cached_matched_articles: list[RankedArticleSchema] = field(default_factory=list)

    # -----------------------------------------------------------------------
    # Stage 3 — Query Generation
    # -----------------------------------------------------------------------
    search_queries: list[tuple[str, str]] = field(default_factory=list)
    # Each tuple: (query_text, query_type_value)

    # -----------------------------------------------------------------------
    # Stage 4/5 — Source Search + Evidence Retrieval
    # -----------------------------------------------------------------------
    candidate_urls: list[CandidateArticleSchema] = field(default_factory=list)
    search_provider_used: str | None = None  # Which provider succeeded first

    # -----------------------------------------------------------------------
    # Stage 6 — Article Extraction
    # -----------------------------------------------------------------------
    extracted_articles: list[RankedArticleSchema] = field(default_factory=list)
    # Articles that failed extraction (URLs only, for logging)
    failed_extraction_urls: list[str] = field(default_factory=list)

    # -----------------------------------------------------------------------
    # Stage 7 — Evidence Ranking
    # -----------------------------------------------------------------------
    ranked_articles: list[RankedArticleSchema] = field(default_factory=list)
    # top_article is the highest-ranked after Stage 7
    top_article: RankedArticleSchema | None = None

    # -----------------------------------------------------------------------
    # Stage 8 — Similarity Analysis
    # -----------------------------------------------------------------------
    scores: VerificationScoresSchema = field(
        default_factory=VerificationScoresSchema
    )
    claim_entities: list[str] = field(default_factory=list)
    claim_keywords: list[str] = field(default_factory=list)
    claim_numerals: list[str] = field(default_factory=list)
    article_entities: list[str] = field(default_factory=list)
    article_numerals: list[str] = field(default_factory=list)

    # -----------------------------------------------------------------------
    # Stage 9 — Contradiction Detection
    # -----------------------------------------------------------------------
    nli_scores: NLIScoresSchema | None = None

    # -----------------------------------------------------------------------
    # Stage 10 — Manipulation Detection
    # -----------------------------------------------------------------------
    manipulation_flags: ManipulationFlagsSchema = field(
        default_factory=ManipulationFlagsSchema
    )
    detected_manipulations: list[ManipulationType] = field(default_factory=list)

    # -----------------------------------------------------------------------
    # Stage 11 — Classification
    # -----------------------------------------------------------------------
    label: VerificationLabel | None = None
    confidence: float = 0.0
    reasoning: str = ""

    # -----------------------------------------------------------------------
    # Stage 12 — Persistence
    # -----------------------------------------------------------------------
    result_id: uuid.UUID | None = None
    persisted: bool = False

    # -----------------------------------------------------------------------
    # Pipeline metadata
    # -----------------------------------------------------------------------
    pipeline_start_time: datetime = field(default_factory=datetime.utcnow)
    stage_timings: dict[str, int] = field(default_factory=dict)
    # stage_id (str value) → wall-clock milliseconds
    stage_errors: dict[str, str] = field(default_factory=dict)
    # stage_id (str value) → error message for non-fatal failures
    pending_log_entries: list[Any] = field(default_factory=list)
    # List of VerificationLog ORM instances, flushed in Stage 12
    fatal_error: str | None = None
    # Set by orchestrator on unrecoverable exception — pipeline aborts

    # -----------------------------------------------------------------------
    # Convenience properties
    # -----------------------------------------------------------------------

    @property
    def has_body(self) -> bool:
        """True if a non-empty normalized news body is available."""
        return bool(self.normalized_body and len(self.normalized_body.strip()) > 10)

    @property
    def has_evidence(self) -> bool:
        """True if at least one ranked article was successfully extracted."""
        return len(self.ranked_articles) > 0

    @property
    def has_fatal_error(self) -> bool:
        """True if the pipeline was aborted due to an unrecoverable error."""
        return self.fatal_error is not None

    @property
    def elapsed_ms(self) -> int:
        """Total wall-clock milliseconds since pipeline start."""
        delta = datetime.utcnow() - self.pipeline_start_time
        return int(delta.total_seconds() * 1000)

    @property
    def stage_error_count(self) -> int:
        """Number of non-fatal stage errors accumulated so far."""
        return len(self.stage_errors)

    def record_stage_error(self, stage_id: PipelineStageID, message: str) -> None:
        """
        Record a non-fatal error for a pipeline stage.

        Non-fatal errors degrade the confidence of the final result but do not
        abort the pipeline. The orchestrator uses `stage_errors` to apply a
        confidence penalty in Stage 11.

        Args:
            stage_id: The stage that encountered the error.
            message:  Human-readable error description.
        """
        self.stage_errors[stage_id.value] = message

    def record_stage_timing(self, stage_id: PipelineStageID, duration_ms: int) -> None:
        """
        Record how long a stage took in milliseconds.

        Args:
            stage_id:    The completed stage.
            duration_ms: Wall-clock time in milliseconds.
        """
        self.stage_timings[stage_id.value] = duration_ms

    def update_scores(self, **kwargs: float | None) -> None:
        """
        Merge new score values into the shared `scores` object.

        Accepts keyword arguments matching VerificationScoresSchema field names.
        Only non-None values overwrite existing scores — this preserves scores
        from earlier stages when a later stage only updates a subset.

        Args:
            **kwargs: Field names from VerificationScoresSchema → new values.

        Example::

            context.update_scores(
                semantic_similarity=0.91,
                entity_match=0.85,
            )
        """
        current = self.scores.model_dump()
        for key, val in kwargs.items():
            if val is not None:
                current[key] = val
        self.scores = VerificationScoresSchema(**current)


# ---------------------------------------------------------------------------
# PipelineStage Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class PipelineStage(Protocol):
    """
    Structural protocol that every pipeline stage must satisfy.

    All 12 stages (S01–S12) implement this protocol. The orchestrator
    calls `execute(context)` on each stage in sequence.

    The stage is responsible for:
    1. Reading needed inputs from `context`.
    2. Performing its work (normalisation, search, extraction, ML inference…).
    3. Writing its outputs back into `context`.
    4. Recording any non-fatal errors via `context.record_stage_error()`.
    5. NOT raising exceptions for recoverable failures — the stage should
       log, record the error, and return the context with degraded data.
       Only truly unrecoverable errors (e.g. DB connection lost) should
       propagate as exceptions to the orchestrator.

    Attributes:
        stage_id: The PipelineStageID enum value identifying this stage.
                  Used by the orchestrator for logging and timing.
    """

    stage_id: PipelineStageID

    async def execute(self, context: PipelineContext) -> PipelineContext:
        """
        Execute this pipeline stage against the provided context.

        Args:
            context: The shared mutable pipeline context carrying all
                     accumulated state from previous stages.

        Returns:
            The same context object (mutated in-place) with this stage's
            outputs written into the appropriate fields.

        Note:
            Stages should NEVER replace the context object — always mutate
            and return the same instance to preserve state from earlier stages.
        """
        ...


def build_context(
    headline: str,
    claimed_source: str,
    *,
    news_body: str | None = None,
    published_date: date | None = None,
    force_refresh: bool = False,
    claim_id: uuid.UUID | None = None,
) -> PipelineContext:
    """
    Construct a fully initialised PipelineContext from raw request inputs.

    This is the canonical way to create a context before passing it to
    `PipelineOrchestrator.run()`. Called by `VerificationService` after
    creating the initial DB record.
    """
    return PipelineContext(
        request_id=uuid.uuid4(),
        claim_id=claim_id,
        raw_headline=headline,
        raw_news_body=news_body,
        raw_claimed_source=claimed_source,
        published_date=published_date,
        force_refresh=force_refresh,
        pipeline_start_time=datetime.utcnow(),
    )


