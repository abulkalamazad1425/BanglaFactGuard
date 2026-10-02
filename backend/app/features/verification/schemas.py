from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator

from app.core.constants import (
    CheckState,
    ClaimScope,
    ContentStatus,
    DateStatus,
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


class VerificationScoresSchema(BaseModel):
    """Measurements, not probabilities of truth. A null value means "no
    measurement" — the reason is in `AnalysisDetails.metrics[<name>].state`
    (NOT_APPLICABLE / EMPTY / UNAVAILABLE), never 0% or 100%."""

    semantic_similarity: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description=(
            "Applicable semantic similarity. HEADLINE_ONLY: headline vs source "
            "title. HEADLINE_WITH_BODY: 0.3*headline + 0.7*body (both applicable)."
        ),
    )
    entity_match: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Directional coverage of the claim's entities in the source evidence (no penalty for extra source entities).",
    )
    keyword_overlap: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Headline keyword coverage against the source title (alias of headline_keyword_coverage).",
    )
    numerical_consistency: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Share of claimed numbers supported by the source; null when the claim has no numbers.",
    )
    contradiction_score: float | None = Field(default=None, ge=0.0, le=1.0)

    headline_similarity: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Embedding cosine similarity between the submitted headline and the source title.",
    )
    body_similarity: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description=(
            "Submitted body vs aligned source passages. NULL (not applicable) "
            "unless a body was submitted - never computed for photo cards."
        ),
    )
    passage_similarity: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Headline vs the most relevant source passages (supporting evidence; not a body match).",
    )
    headline_keyword_coverage: float | None = Field(default=None, ge=0.0, le=1.0)
    passage_keyword_coverage: float | None = Field(default=None, ge=0.0, le=1.0)
    body_keyword_coverage: float | None = Field(default=None, ge=0.0, le=1.0)

    model_config = {
        "json_schema_extra": {
            "example": {
                "semantic_similarity": 0.91,
                "entity_match": 0.85,
                "keyword_overlap": 0.78,
                "numerical_consistency": 1.0,
                "contradiction_score": 0.04,
            }
        }
    }


class AlteredNumberDetail(BaseModel):
    """One number present in the claim but absent from the article, with the
    closest number the article did contain (if any) — e.g. claimed "১০০ জন"
    where the article says "১০ জন" surfaces as claimed="১০০ জন",
    nearest_in_article="১০"."""

    claimed: str
    nearest_in_article: str | None = Field(
        default=None,
        description="Closest numeral actually found in the article, or null if none was close.",
    )


class SubstitutedEntityDetail(BaseModel):
    """A same-type entity substitution S10 detected — e.g. the claim names a
    PER the article never mentions, while the article names a different PER
    of the same role."""

    entity_type: str = Field(description="PER, LOC, or ORG")
    claimed: list[str]
    article_same_type: list[str] = Field(
        description="Entities of the same type the article mentions instead."
    )


class DiscrepancyDetail(BaseModel):
    """One concrete, quotable disagreement between the claim and the source."""

    kind: str = Field(
        description="numbers | negation | entity_substitution | entity_role | scope | attribution | modality"
    )
    claim_text: str
    evidence_text: str | None = None
    detail: str
    part: str = Field(default="headline", description="headline | body")


class ManipulationFlagsSchema(BaseModel):
    """Alteration findings. A boolean is True ONLY when a concrete discrepancy
    was found; False does NOT mean "verified" - consult `check_states`, where
    a check that did not run is NOT_EVALUATED and one that does not apply is
    NOT_APPLICABLE. Rows persisted before check_states existed have an empty
    map and must be read as "not evaluated"."""

    headline_manipulated: bool = Field(default=False)
    body_altered: bool = Field(default=False)
    numbers_altered: bool = Field(default=False)
    entities_replaced: bool = Field(default=False)

    altered_numbers: list[AlteredNumberDetail] = Field(
        default_factory=list,
        description="Set when numbers_altered is True: which claimed numbers differ from the source, and the source's number.",
    )
    substituted_entities: list[SubstitutedEntityDetail] = Field(
        default_factory=list,
        description="Set when entities_replaced is True: which claimed entity replaced which source entity (same type and role).",
    )
    check_states: dict[str, CheckState] = Field(
        default_factory=dict,
        description=(
            "headline | body | numbers | negation | entities | scope | "
            "attribution | modality -> PASSED | FAILED | NOT_EVALUATED | NOT_APPLICABLE"
        ),
    )
    discrepancies: list[DiscrepancyDetail] = Field(default_factory=list)

    @property
    def any_manipulation_detected(self) -> bool:
        return any(
            [
                self.headline_manipulated,
                self.body_altered,
                self.numbers_altered,
                self.entities_replaced,
            ]
        ) or bool(self.discrepancies)

    model_config = {
        "json_schema_extra": {
            "example": {
                "headline_manipulated": True,
                "body_altered": False,
                "numbers_altered": True,
                "entities_replaced": False,
                "altered_numbers": [{"claimed": "5", "nearest_in_article": "10"}],
                "substituted_entities": [],
                "check_states": {"numbers": "FAILED", "body": "NOT_APPLICABLE"},
                "discrepancies": [],
            }
        }
    }


class MetricDetail(BaseModel):
    state: MetricState
    value: float | None = None
    reason: str | None = None
    details: dict = Field(default_factory=dict)


class EvidencePassage(BaseModel):
    text: str
    score: float
    location: str = Field(default="body", description="title | body")
    first_sentence: int | None = None
    last_sentence: int | None = None


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


class NLIAnalysis(BaseModel):
    entailment: float | None = None
    neutral: float | None = None
    contradiction: float | None = None
    premise: str | None = Field(default=None, description="relevant_passages | title_only")
    reliability: str = Field(
        default="UNVALIDATED_FOR_BANGLA",
        description="The NLI model has not been validated on Bangla; it can block MATCHED but never alone cause ALTERED.",
    )


class AnalysisDetails(BaseModel):
    """Everything needed to explain and reproduce a result after Redis expiry."""

    pipeline_version: str | None = None
    claim_scope: ClaimScope | None = None
    metrics: dict[str, MetricDetail] = Field(default_factory=dict)
    passages: list[EvidencePassage] = Field(default_factory=list)
    nli: NLIAnalysis | None = None
    search: SearchAccounting | None = None
    date: DateAnalysis | None = None
    source_basis: list[str] = Field(default_factory=list)
    content_basis: list[str] = Field(default_factory=list)
    stage_errors: dict[str, str] = Field(default_factory=dict)


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


class VerificationScoresResponse(VerificationScoresSchema):
    pass


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
            "How the claimed content compares to the source. Only set when "
            "source_status is CONFIRMED — there is nothing to compare "
            "against when the source never published the story."
        ),
    )
    date_status: DateStatus | None = Field(
        default=None,
        description=(
            "Whether the claimed publication date matches the source "
            "article's actual date. Only set when both dates are known; a "
            "mismatch does not imply the content itself is false."
        ),
    )
    confidence: float = Field(..., ge=0.0, le=1.0)
    reasoning: str
    matched_articles: list[RankedArticleSchema] = Field(default_factory=list)
    scores: VerificationScoresResponse
    manipulation_flags: ManipulationFlagsSchema = Field(
        default_factory=ManipulationFlagsSchema
    )
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
            "Automated check strength: the mean of the applicable similarity/"
            "coverage measurements behind this result. It is a measurement "
            "summary, not the probability that the claim is true."
        ),
    )
    pipeline_version: str | None = None
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
                "scores": {
                    "semantic_similarity": 0.91,
                    "entity_match": 0.88,
                    "keyword_overlap": 0.79,
                    "numerical_consistency": 1.0,
                    "contradiction_score": 0.04,
                },
                "manipulation_flags": {
                    "headline_manipulated": False,
                    "body_altered": False,
                    "numbers_altered": False,
                    "entities_replaced": False,
                },
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
