"""
app/schemas/scores.py
======================
Pydantic schemas for the multi-dimensional scoring output of the verification
pipeline (Stages 8–10) and manipulation detection flags (Stage 10).

Design decisions:
- Every score field is `float | None` (nullable) because a stage may fail
  gracefully and return `None` for its score rather than crashing the pipeline.
  The classifier (Stage 11) handles `None` scores via conservative defaults.
- `ge=0.0, le=1.0` validators enforce the [0, 1] score range at the
  schema boundary — matching the DB CHECK constraints in VerificationResult.
- `ManipulationFlagsSchema` is a flat boolean struct rather than a list of
  enums, making it easier to serialise to JSON and query in the API response.
- `NLIScoresSchema` exposes the raw entailment/contradiction/neutral
  probability triple for full transparency, in addition to the derived
  `contradiction_score` in `VerificationScoresSchema`.

Usage in the pipeline context::

    from app.schemas.scores import VerificationScoresSchema
    scores = VerificationScoresSchema(
        semantic_similarity=0.91,
        entity_match=0.85,
        keyword_overlap=0.78,
        numerical_consistency=1.0,
        contradiction_score=0.04,
    )
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class NLIScoresSchema(BaseModel):
    """
    Raw output triple from the NLI cross-encoder model (Stage 9).

    The three values sum to approximately 1.0 (softmax output).
    Used internally by the pipeline; the `contradiction_score` field in
    `VerificationScoresSchema` is derived from this.

    Attributes:
        entailment:    Probability that the article SUPPORTS the claim.
        contradiction: Probability that the article CONTRADICTS the claim.
        neutral:       Probability that the article is neither for nor against.
    """

    entailment: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="NLI entailment probability — article supports the claim",
    )
    contradiction: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="NLI contradiction probability — article contradicts the claim",
    )
    neutral: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="NLI neutral probability — article neither supports nor contradicts",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "entailment": 0.87,
                "contradiction": 0.05,
                "neutral": 0.08,
            }
        }
    }


class VerificationScoresSchema(BaseModel):
    """
    Aggregated multi-dimensional evidence scores for a verification result.

    Each dimension captures a different facet of the relationship between
    the submitted claim and the best-matching retrieved article:

    Attributes:
        semantic_similarity:   LaBSE cosine similarity in [0, 1].
                               High → claim and article are semantically close.
        entity_match:          Bangla NER entity set-intersection ratio in [0, 1].
                               High → same persons, places, organisations mentioned.
        keyword_overlap:       Jaccard similarity of extracted keyword sets in [0, 1].
                               High → shared topical vocabulary.
        numerical_consistency: Proportion of claim numerals found in the article [0, 1].
                               High → numbers not altered (dates, statistics, counts).
        contradiction_score:   NLI contradiction probability in [0, 1].
                               High → article actively contradicts the claim.
    """

    semantic_similarity: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="LaBSE cosine similarity between claim and best article [0, 1]",
    )
    entity_match: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="NER entity set-intersection ratio [0, 1]",
    )
    keyword_overlap: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Jaccard keyword overlap between claim and article [0, 1]",
    )
    numerical_consistency: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Proportion of claim numerals found verbatim in the article [0, 1]",
    )
    contradiction_score: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="NLI contradiction probability from DeBERTa cross-encoder [0, 1]",
    )

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


class ManipulationFlagsSchema(BaseModel):
    """
    Boolean flags produced by Stage 10 (Manipulation Detector) indicating
    which types of manipulation were detected in the claim relative to the
    best-matching article.

    Multiple flags can be True simultaneously — e.g. a manipulated article
    may have both a changed headline AND altered numbers.

    Attributes:
        headline_manipulated:    Headline does not match the article title,
                                 but the body is largely consistent.
        body_altered:            Article body significantly diverges from the claim body.
        numbers_altered:         One or more numerical values were changed.
        entities_replaced:       Named entities (persons, places, orgs) were substituted.
    """

    headline_manipulated: bool = Field(
        default=False,
        description="Headline differs from matched article title while body is consistent",
    )
    body_altered: bool = Field(
        default=False,
        description="Article body significantly diverges from the matched article",
    )
    numbers_altered: bool = Field(
        default=False,
        description="One or more numerical values in the claim do not match the article",
    )
    entities_replaced: bool = Field(
        default=False,
        description="Named entities (persons/places/orgs) in the claim differ from the article",
    )

    @property
    def any_manipulation_detected(self) -> bool:
        """Return True if any manipulation flag is set."""
        return any(
            [
                self.headline_manipulated,
                self.body_altered,
                self.numbers_altered,
                self.entities_replaced,
            ]
        )

    model_config = {
        "json_schema_extra": {
            "example": {
                "headline_manipulated": True,
                "body_altered": False,
                "numbers_altered": False,
                "entities_replaced": False,
            }
        }
    }
