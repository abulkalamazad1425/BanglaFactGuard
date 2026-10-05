from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator

from app.core.constants import (
    BodyComparisonStatus,
    ClaimScope,
    ContentStatus,
    DateStatus,
    HeadlineCheckStatus,
    MetricState,
    OverallVerdict,
    SourceStatus,
    SubmissionStatus,
)
from app.features.articles.schemas import RankedArticleSchema


class NLIScoresSchema(BaseModel):

    entailment: float = Field(
        ..., ge=0.0, le=1.0, description="NLI entailment probability"
    )
    contradiction: float = Field(
        ..., ge=0.0, le=1.0, description="NLI contradiction probability"
    )
    neutral: float = Field(..., ge=0.0, le=1.0, description="NLI neutral probability")

    model_config = {
        "json_schema_extra": {
            "example": {"entailment": 0.87, "contradiction": 0.05, "neutral": 0.08}
        }
    }


class MetricDetail(BaseModel):
    """A source-correspondence measurement plus the state that explains it.
    A null value is "no measurement" (see `state`), never 0."""

    state: MetricState
    value: float | None = None
    reason: str | None = None
    details: dict = Field(default_factory=dict)


class SearchAccounting(BaseModel):
    attempted: int = 0
    success: int = 0
    success_empty: int = 0
    failed: int = 0
    skipped: int = 0
    cached: int = 0
    adequate: bool | None = Field(
        default=None,
        description="True only when enough provider calls completed to treat an empty result as a real negative.",
    )
    providers: dict[str, dict[str, int]] = Field(default_factory=dict)
    redirect_rejected: int = 0


class DateAnalysis(BaseModel):
    claimed_date: date | None = None
    article_date: date | None = Field(
        default=None, description="datePublished as a calendar day in Asia/Dhaka."
    )
    article_published_at: datetime | None = None
    provenance: str | None = Field(
        default=None,
        description="Where the article's publication date came from (json_ld.datePublished, meta.article:published_time, selector, ...). dateModified and crawl dates are never used.",
    )
    tz_assumed: bool = False
    timezone: str = "Asia/Dhaka"


class HeadlineDifference(BaseModel):
    """One material difference between the claim headline and the source title."""

    kind: str = Field(
        description="numbers | date | negation | modality | scope | subject_object | attribution | denial | entity | main_point"
    )
    detail: str
    claim_text: str
    source_text: str


class HeadlineSemanticAssessment(BaseModel):
    """Local-model evidence for a non-exact comparison (title vs headline only)."""

    available: bool
    entailment_title_to_claim: float | None = Field(default=None, ge=0.0, le=1.0)
    contradiction_title_to_claim: float | None = Field(default=None, ge=0.0, le=1.0)
    entailment_claim_to_title: float | None = Field(default=None, ge=0.0, le=1.0)
    contradiction_claim_to_title: float | None = Field(default=None, ge=0.0, le=1.0)
    embedding_cosine: float | None = Field(
        default=None, ge=-1.0, le=1.0, description="LaBSE cosine of headline vs title (raw, -1..1)."
    )
    reason: str | None = None


class HeadlineAlterationDetail(BaseModel):
    """Headline Alteration — the claim headline compared ONLY with the
    selected source article's title (never its body). `verdict` is MATCHED,
    ALTERED or null; when null, `status` says why (source not found, search
    incomplete, title missing, model unavailable, undetermined)."""

    status: HeadlineCheckStatus
    verdict: ContentStatus | None = None
    reason: str = Field(description="Short, evidence-based basis for the verdict or for its absence.")
    exact_match: bool = Field(
        default=False,
        description="True when the verdict was decided by an exact match, before any alteration analysis ran.",
    )
    basis: str = Field(
        default="none",
        description="exact | same_words | semantic_equivalence | material_difference | semantic_divergence | none",
    )
    claim_headline: str
    source_title: str | None = None
    source_publisher: str | None = None
    source_url: str | None = None
    differences: list[HeadlineDifference] = Field(default_factory=list)
    semantic: HeadlineSemanticAssessment | None = None
    ner_available: bool = False
    method: str | None = None


class BodySimilarityMetric(BaseModel):
    """One claim-body vs source-body similarity measurement. `value` is the
    displayed 0-1 score (null when unavailable - never a default 0);
    `raw_value` keeps the metric's raw output (semantic cosine may be
    negative); `reason` explains unavailability."""

    available: bool
    value: float | None = Field(default=None, ge=0.0, le=1.0)
    raw_value: float | None = None
    reason: str | None = None
    details: dict = Field(default_factory=dict)


class BodySimilarityReport(BaseModel):
    """Claim body vs source body - similarity MEASUREMENTS only, never a
    truth, alteration or contradiction verdict, and never an input to the
    Headline Alteration verdict."""

    status: BodyComparisonStatus
    reason: str | None = None
    tfidf_cosine: BodySimilarityMetric | None = None
    jaccard: BodySimilarityMetric | None = None
    normalized_levenshtein: BodySimilarityMetric | None = None
    semantic_cosine: BodySimilarityMetric | None = None
    claim_chars: int | None = None
    source_chars: int | None = None


class ExecutionTimings(BaseModel):
    """Measured wall times for this execution, in milliseconds.

    Pipeline time excludes photo preprocessing, queue wait and the final
    transaction commit. Missing stages were skipped, not measured as zero.
    """

    stage_ms: dict[str, int] = Field(default_factory=dict)
    preprocessing_ms: dict[str, int] = Field(default_factory=dict)
    pipeline_ms: int
    cache_hit: bool = False


class AnalysisDetails(BaseModel):
    """Everything needed to explain and reproduce a result after Redis expiry."""

    pipeline_version: str | None = None
    claim_scope: ClaimScope | None = None
    metrics: dict[str, MetricDetail] = Field(
        default_factory=dict, description="Source-correspondence measurements."
    )
    search: SearchAccounting | None = None
    source_basis: list[str] = Field(default_factory=list)
    headline_alteration: HeadlineAlterationDetail | None = None
    body_similarity: BodySimilarityReport | None = None
    date: DateAnalysis | None = None
    stage_errors: dict[str, str] = Field(default_factory=dict)
    timings: ExecutionTimings | None = None


class VerificationRequest(BaseModel):

    headline: str = Field(
        ...,
        min_length=5,
        max_length=2000,
        description="The article headline being claimed.",
        examples=["বাংলাদেশে নতুন ডিজিটাল নিরাপত্তা আইন পাস হয়েছে"],
    )
    body_text: str | None = Field(default=None, max_length=50_000)
    claimed_source_text: str = Field(..., min_length=1, max_length=255)
    published_date: date | None = Field(default=None, examples=["2024-03-15"])
    force_refresh: bool = Field(default=False)

    @field_validator("headline")
    @classmethod
    def _strip_headline(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("headline must not be blank after stripping whitespace")
        return stripped

    @field_validator("claimed_source_text")
    @classmethod
    def _strip_claimed_source(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("claimed_source_text must not be blank")
        return stripped

    @field_validator("body_text")
    @classmethod
    def _strip_body_text(cls, v: str | None) -> str | None:
        if v is None:
            return None
        stripped = v.strip()
        return stripped if stripped else None

    model_config = {
        "json_schema_extra": {
            "example": {
                "headline": "বাংলাদেশে নতুন ডিজিটাল নিরাপত্তা আইন পাস হয়েছে",
                "body_text": "জাতীয় সংসদে আজ বিকেলে ডিজিটাল নিরাপত্তা আইনের সংশোধনী প্রস্তাব সর্বসম্মতিক্রমে পাস হয়েছে।",
                "claimed_source_text": "প্রথম আলো",
                "published_date": "2024-03-15",
                "force_refresh": False,
            }
        }
    }


class VerificationResponse(BaseModel):

    submission_id: uuid.UUID
    overall_verdict: OverallVerdict | None = Field(
        default=None,
        description=(
            "The expert-finalized Overall verdict (Fake/Real/Misleading/Altered). "
            "The automated system never computes this — it is NULL until expert "
            "review finalizes the claim, full stop. There is no AI-implied value."
        ),
    )
    is_finalized: bool = Field(
        default=False,
        description="True once expert review has finalized overall_verdict.",
    )
    was_overridden: bool = Field(
        default=False,
        description=(
            "True if expert review's finalized source/content/date status "
            "differs from the AI's original structured call on any dimension. "
            "Not applicable to overall_verdict, which the AI never sets."
        ),
    )
    ai_source_status: SourceStatus | None = Field(
        default=None,
        description="The AI's own original call — immutable, never changed by expert review.",
    )
    ai_content_status: ContentStatus | None = Field(default=None)
    ai_date_status: DateStatus | None = Field(default=None)
    source_status: SourceStatus = Field(
        ...,
        description=(
            "The displayed Source verdict — expert-finalized if available, "
            "otherwise the AI's call (see ai_source_status for the AI's "
            "original, which this may now differ from)."
        ),
    )
    content_status: ContentStatus | None = Field(
        default=None,
        description=(
            "Headline Alteration verdict (MATCHED | ALTERED): the claim headline "
            "compared with the source title only. Null when no verdict was "
            "reached - see headline_check_status for why."
        ),
    )
    headline_check_status: HeadlineCheckStatus | None = Field(
        default=None,
        description="Processing/availability status of the Headline Alteration check (separate from the verdict).",
    )
    date_status: DateStatus | None = Field(
        default=None,
        description=(
            "Whether the claimed publication date matches the source "
            "article's actual date. Only set when both dates are known; a "
            "mismatch does not imply the content itself is false."
        ),
    )
    confidence: float = Field(
        ..., ge=0.0, le=1.0,
        description="Source-correspondence strength (mean of the correspondence measurements). Not a probability of truth.",
    )
    reasoning: str
    matched_articles: list[RankedArticleSchema] = Field(default_factory=list)
    normalized_source: str | None = None
    cached: bool = False
    processing_time_ms: int | None = None
    created_at: datetime
    claim_scope: ClaimScope | None = Field(
        default=None,
        description="HEADLINE_ONLY (always for photo cards) or HEADLINE_WITH_BODY.",
    )
    review_pending: bool = Field(
        default=True,
        description="True until expert review finalizes the overall verdict; the UI must not show a truth badge while True.",
    )
    confidence_meaning: str = Field(
        default=(
            "Source-correspondence strength: the mean of the headline/title "
            "similarity and keyword-coverage measurements used to decide "
            "whether the claimed outlet carried this report. It is not the "
            "probability that the claim is true."
        ),
    )
    pipeline_version: str | None = None
    legacy_result: bool = Field(
        default=False,
        description=(
            "True for a result stored by the pre-Headline-Alteration pipeline. Its "
            "old content-level verdict is NOT shown as a headline verdict "
            "(ai_content_status is null for such rows)."
        ),
    )
    analysis: AnalysisDetails | None = None

    model_config = {
        "json_schema_extra": {
            "example": {
                "submission_id": "550e8400-e29b-41d4-a716-446655440000",
                "source_status": "CONFIRMED",
                "content_status": "MATCHED",
                "date_status": "MISMATCHED",
                "confidence": 0.92,
                "reasoning": (
                    "Prothom Alo published a matching article, but on a "
                    "different date than claimed."
                ),
                "matched_articles": [],
                "headline_check_status": "COMPLETED",
                "normalized_source": "prothomalo.com",
                "cached": False,
                "processing_time_ms": 4231,
                "created_at": "2024-03-15T12:00:00Z",
            }
        }
    }


class VerificationResultSummary(BaseModel):

    submission_id: uuid.UUID
    headline: str = Field(..., max_length=200)
    source_status: SourceStatus
    content_status: ContentStatus | None = None
    date_status: DateStatus | None = None
    confidence: float = Field(..., ge=0.0, le=1.0)
    claimed_source_text: str
    normalized_source: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class VerificationQueuedResponse(BaseModel):
    """Acknowledgement for a claim accepted for background verification.

    The pipeline takes up to a minute or so, which is far too long to hold a
    user on the form. The claim is registered immediately and this identifier
    is what the caller polls (or revisits from their history) for the result.
    """

    submission_id: uuid.UUID
    status: SubmissionStatus
    cached: bool = Field(
        default=False,
        description=(
            "True when this exact claim had already been verified and the "
            "stored result is being reused instead of re-running the pipeline."
        ),
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "submission_id": "550e8400-e29b-41d4-a716-446655440000",
                "status": "PENDING",
                "cached": False,
            }
        }
    }


class VerificationStatusResponse(BaseModel):

    submission_id: uuid.UUID
    status: SubmissionStatus
    phase: str | None = Field(
        default=None, description="QUEUED | EXTRACTING | VERIFYING | DONE | FAILED"
    )
    result: VerificationResponse | None = None
    error: str | None = Field(default=None, description="User-presentable reason when status is FAILED")
    queued_at: datetime
    updated_at: datetime

    model_config = {
        "json_schema_extra": {
            "example": {
                "submission_id": "550e8400-e29b-41d4-a716-446655440000",
                "status": "PROCESSING",
                "result": None,
                "error": None,
                "queued_at": "2024-03-15T12:00:00Z",
                "updated_at": "2024-03-15T12:00:03Z",
            }
        }
    }
