"""
app/pipelines/stages/s11_classifier.py
========================================
Stage 11: Verdict Classification (CRITICAL)

## Responsibility

Combine all evidence signals into a final VerificationLabel verdict and
confidence score, with a human-readable reasoning explanation.

## Classification logic

### Step 1: Evidence presence check
If no ranked articles exist → NOT_FOUND_IN_CLAIMED_SOURCE (confidence=0.95).

### Step 2: Score aggregation
Compute a weighted evidence score from available dimensions:

    evidence_score = (
        W_SEM * semantic_similarity  +
        W_ENT * entity_match         +
        W_KW  * keyword_overlap      +
        W_NUM * numerical_consistency
    ) — adjusted for contradiction

    Weights: W_SEM=0.45, W_ENT=0.25, W_KW=0.15, W_NUM=0.15

Contradiction penalty: if contradiction_score > 0.5, subtract
(contradiction_score - 0.5) * 0.4 from the evidence score.

### Step 3: Label assignment (runtime-configurable thresholds)

    evidence_score ≥ TRUE_THRESHOLD   → TRUE
    evidence_score ≥ PARTIAL_THRESHOLD AND any_manipulation → PARTIALLY_TRUE
    evidence_score ≥ PARTIAL_THRESHOLD → TRUE (high body sim, minor difference)
    evidence_score ≥ FALSE_THRESHOLD  → PARTIALLY_TRUE
    else                               → FALSE

    Override: contradiction_score > CONTRADICTION_THRESHOLD → FALSE

### Step 4: Confidence calculation
Confidence is derived from |evidence_score - decision_boundary| so the model
expresses lower confidence near thresholds.

### Step 5: Reasoning generation
A structured natural-language reasoning string is assembled from available
evidence scores and manipulation flags.

## Criticality: CRITICAL
If classification fails, the orchestrator aborts and marks the claim as FAILED.
"""

from __future__ import annotations

import structlog

from app.core.config import get_settings
from app.core.constants import ManipulationType, PipelineStageID, VerificationLabel
from app.core.exceptions import ClassificationError
from app.features.verification.pipeline.context import PipelineContext

logger = structlog.get_logger(__name__)
_SETTINGS = get_settings()

# Score aggregation weights
_W_SEM = 0.45
_W_ENT = 0.25
_W_KW = 0.15
_W_NUM = 0.15


class ClassifierStage:
    """
    Stage 11 (CRITICAL): Compute final verdict, confidence, and reasoning.

    No external ML dependencies — classification is rule-based using
    the scores accumulated in Stages 8–10. This makes classification:
    - Deterministic and auditable
    - Configurable at runtime (threshold values in AppSettings)
    - Testable without loading any ML models
    """

    stage_id = PipelineStageID.S11_CLASSIFIER

    async def execute(self, context: PipelineContext) -> PipelineContext:
        """
        Classify the claim and populate label, confidence, and reasoning.

        Args:
            context: Pipeline context with all scores and manipulation flags set.

        Returns:
            Context with label, confidence, and reasoning populated.

        Raises:
            ClassificationError: If classification logic raises an unhandled error.
        """
        thresholds = _SETTINGS.classification

        try:
            # ------------------------------------------------------------------
            # Step 1: Evidence presence check
            # ------------------------------------------------------------------
            if not context.has_evidence:
                context.label = VerificationLabel.NOT_FOUND_IN_CLAIMED_SOURCE
                context.confidence = 0.95
                context.reasoning = self._build_not_found_reasoning(context)
                logger.info(
                    "s11_verdict",
                    label=context.label.value,
                    confidence=context.confidence,
                    reason="no_evidence",
                )
                return context

            # ------------------------------------------------------------------
            # Step 1b: NOT_FOUND gate on semantic similarity
            # If the best article we found is semantically very far from the claim,
            # it means we found the wrong article (e.g. a different news from the
            # same site). Treat this as NOT_FOUND rather than a misleading verdict.
            # ------------------------------------------------------------------
            sem_sim = context.scores.semantic_similarity
            if (
                sem_sim is not None
                and sem_sim < thresholds.not_found_max_semantic_similarity
            ):
                context.label = VerificationLabel.NOT_FOUND_IN_CLAIMED_SOURCE
                context.confidence = round(min(0.90, 0.5 + (thresholds.not_found_max_semantic_similarity - sem_sim) * 2), 3)
                context.reasoning = (
                    f"An article was retrieved from {context.normalized_source or 'the claimed source'}, "
                    f"but its semantic similarity to the claim is too low ({sem_sim:.2f}), "
                    "indicating the retrieved article is unrelated to the claim. "
                    "Verdict: NOT FOUND IN CLAIMED SOURCE."
                )
                logger.info(
                    "s11_verdict",
                    label=context.label.value,
                    confidence=context.confidence,
                    reason="sem_sim_below_not_found_gate",
                    sem_sim=round(sem_sim, 3),
                )
                return context

            # ------------------------------------------------------------------
            # Step 2: Compute weighted evidence score
            # ------------------------------------------------------------------
            scores = context.scores
            evidence_score = _compute_weighted_score(scores)

            # Apply contradiction penalty
            contradiction = scores.contradiction_score or 0.0
            if contradiction > thresholds.contradiction_override_threshold:
                # Strong contradiction → hard override to FALSE
                context.label = VerificationLabel.FALSE
                context.confidence = round(
                    min(0.95, 0.6 + contradiction * 0.35), 3
                )
                context.reasoning = self._build_reasoning(
                    context, VerificationLabel.FALSE, evidence_score
                )
                logger.info(
                    "s11_verdict",
                    label=context.label.value,
                    confidence=context.confidence,
                    reason="contradiction_override",
                    contradiction=round(contradiction, 3),
                )
                return context

            # Soft contradiction penalty
            if contradiction > 0.5:
                penalty = (contradiction - 0.5) * 0.4
                evidence_score = max(0.0, evidence_score - penalty)

            # Degrade score by number of stage errors
            if context.stage_error_count > 0:
                degradation = min(0.15, context.stage_error_count * 0.05)
                evidence_score = max(0.0, evidence_score - degradation)

            # ------------------------------------------------------------------
            # Step 3: Label assignment
            # ------------------------------------------------------------------
            manipulation = context.manipulation_flags
            label = _assign_label(evidence_score, manipulation, thresholds)

            # ------------------------------------------------------------------
            # Step 4: Confidence calculation
            # ------------------------------------------------------------------
            confidence = _compute_confidence(evidence_score, label, thresholds)

            # ------------------------------------------------------------------
            # Step 5: Reasoning
            # ------------------------------------------------------------------
            reasoning = self._build_reasoning(context, label, evidence_score)

            context.label = label
            context.confidence = confidence
            context.reasoning = reasoning

            logger.info(
                "s11_verdict",
                label=label.value,
                confidence=confidence,
                evidence_score=round(evidence_score, 3),
                manipulation=manipulation.any_manipulation_detected,
            )
            return context

        except Exception as exc:
            raise ClassificationError(
                stage_id=self.stage_id.value,
                message=f"Classification failed: {exc}",
            ) from exc

    # ------------------------------------------------------------------
    # Reasoning builders
    # ------------------------------------------------------------------

    def _build_reasoning(
        self,
        context: PipelineContext,
        label: VerificationLabel,
        evidence_score: float,
    ) -> str:
        """Build a structured reasoning explanation string."""
        parts: list[str] = []
        scores = context.scores
        article = context.top_article
        source = context.normalized_source or context.raw_claimed_source
        flags = context.manipulation_flags

        # Source context
        if article:
            parts.append(
                f"A matching article was found on {source or 'the claimed source'}."
            )
        else:
            parts.append(f"No matching article was found on {source or 'the claimed source'}.")

        # Score summary
        if scores.semantic_similarity is not None:
            parts.append(
                f"Semantic similarity: {scores.semantic_similarity:.2f}."
            )
        if scores.entity_match is not None:
            parts.append(f"Entity match: {scores.entity_match:.2f}.")
        if scores.numerical_consistency is not None and scores.numerical_consistency < 1.0:
            parts.append(
                f"Numerical consistency: {scores.numerical_consistency:.2f} "
                "(some numbers may differ)."
            )
        if scores.contradiction_score is not None and scores.contradiction_score > 0.3:
            parts.append(
                f"Contradiction detected (score: {scores.contradiction_score:.2f})."
            )

        # Manipulation flags
        if flags.headline_manipulated:
            parts.append("Headline appears to have been manipulated relative to the original article.")
        if flags.body_altered:
            parts.append("Article body shows significant divergence from the matched article.")
        if flags.numbers_altered:
            parts.append("One or more numerical values appear to have been altered.")
        if flags.entities_replaced:
            parts.append("Named entities (persons/places/organisations) may have been substituted.")

        # Label summary
        label_summary = {
            VerificationLabel.TRUE: "Verdict: The claim is TRUE — the source published matching content.",
            VerificationLabel.FALSE: "Verdict: The claim is FALSE — the article contradicts or significantly differs.",
            VerificationLabel.PARTIALLY_TRUE: "Verdict: The claim is PARTIALLY TRUE — the source published related content with alterations.",
            VerificationLabel.NOT_FOUND_IN_CLAIMED_SOURCE: "Verdict: NOT FOUND IN CLAIMED SOURCE — no matching article was retrieved.",
        }
        parts.append(label_summary.get(label, ""))

        return " ".join(p for p in parts if p)

    def _build_not_found_reasoning(self, context: PipelineContext) -> str:
        """Build reasoning for NOT_FOUND_IN_CLAIMED_SOURCE verdict."""
        source = context.normalized_source or context.raw_claimed_source
        queries_tried = len(context.search_queries)
        return (
            f"No article matching the claim headline was found on {source or 'the claimed source'} "
            f"after executing {queries_tried} search query variant(s) across multiple providers. "
            "Verdict: NOT FOUND IN CLAIMED SOURCE."
        )


# ---------------------------------------------------------------------------
# Pure helper functions
# ---------------------------------------------------------------------------


def _compute_weighted_score(scores) -> float:
    """Compute weighted aggregation of available score dimensions."""
    total_weight = 0.0
    weighted_sum = 0.0

    dim_weights = [
        (scores.semantic_similarity, _W_SEM),
        (scores.entity_match, _W_ENT),
        (scores.keyword_overlap, _W_KW),
        (scores.numerical_consistency, _W_NUM),
    ]

    for value, weight in dim_weights:
        if value is not None:
            weighted_sum += value * weight
            total_weight += weight

    if total_weight == 0:
        return 0.0

    # Normalise by actual total weight (handles missing dimensions)
    return weighted_sum / total_weight


def _assign_label(evidence_score: float, manipulation, thresholds) -> VerificationLabel:
    """Assign a VerificationLabel based on evidence score and manipulation flags."""
    any_manip = manipulation.any_manipulation_detected

    if evidence_score >= thresholds.true_threshold:
        if any_manip:
            return VerificationLabel.PARTIALLY_TRUE
        return VerificationLabel.TRUE

    if evidence_score >= thresholds.partial_threshold:
        return VerificationLabel.PARTIALLY_TRUE

    if evidence_score >= thresholds.false_threshold:
        return VerificationLabel.FALSE

    return VerificationLabel.FALSE


def _compute_confidence(
    evidence_score: float, label: VerificationLabel, thresholds
) -> float:
    """
    Compute confidence as a function of distance from the nearest threshold.

    Near a threshold → low confidence. Far from all thresholds → high confidence.
    """
    # Decision boundaries
    boundaries = [
        thresholds.true_threshold,
        thresholds.partial_threshold,
        thresholds.false_threshold,
    ]
    min_distance = min(abs(evidence_score - b) for b in boundaries)

    # Base confidence: higher when far from any boundary
    base = 0.5 + min_distance * 1.5
    confidence = round(min(0.97, max(0.50, base)), 3)
    return confidence

