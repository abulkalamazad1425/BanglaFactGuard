from __future__ import annotations

import math

import structlog

from app.core.config import get_settings
from app.core.constants import ContentStatus, DateStatus, PipelineStageID, SourceStatus
from app.core.exceptions import ClassificationError
from app.features.verification.pipeline.context import PipelineContext

logger = structlog.get_logger(__name__)
_SETTINGS = get_settings()


_W_SEM = 0.45
_W_ENT = 0.25
_W_KW = 0.15
_W_NUM = 0.15


assert (
    abs((_W_SEM + _W_ENT + _W_KW + _W_NUM) - 1.0) < 1e-9
), f"Score aggregation weights must sum to 1.0, got {_W_SEM + _W_ENT + _W_KW + _W_NUM}"


class ClassifierStage:
    """Produces the three-dimensional verdict: source, content, date.

    The three checks run in order and each is independent of the others:

    1. Source — does the claimed source carry this story at all? If not,
       content and date are left unset: there is nothing to compare a claim's
       wording or date against when the source never published it.
    2. Content — once the source is CONFIRMED, does the claimed content
       carry the same facts as the source (MATCHED), or have material facts
       changed (ALTERED)? Paraphrase and reordering are MATCHED; changed
       numbers, names, outcomes, or outright contradiction are ALTERED.
    3. Date — does the claimed publication date match the source's actual
       date? This is purely informational: a date mismatch never demotes
       content_status, and is left unset when either date is unknown.
    """

    stage_id = PipelineStageID.S11_CLASSIFIER

    async def execute(self, context: PipelineContext) -> PipelineContext:
        thresholds = _SETTINGS.classification

        try:

            if not context.has_evidence:
                self._set_not_found(context, reason="no_evidence")
                return context

            sem_sim = context.scores.semantic_similarity
            if (
                sem_sim is not None
                and sem_sim < thresholds.not_found_max_semantic_similarity
            ):
                self._set_not_found(
                    context,
                    reason="sem_sim_below_not_found_gate",
                    sem_sim=sem_sim,
                )
                return context

            context.source_status = SourceStatus.CONFIRMED

            scores = context.scores
            evidence_score = _compute_weighted_score(scores, thresholds)

            contradiction = scores.contradiction_score or 0.0
            contradiction_override = contradiction > thresholds.contradiction_override_threshold

            if contradiction > 0.5 and not contradiction_override:
                penalty = (contradiction - 0.5) * 0.4
                evidence_score = max(0.0, evidence_score - penalty)

            if context.stage_error_count > 0:
                degradation = min(0.15, context.stage_error_count * 0.05)
                evidence_score = max(0.0, evidence_score - degradation)

            manipulation = context.manipulation_flags
            content_status = _assign_content_status(
                evidence_score, manipulation, contradiction_override, thresholds
            )
            context.content_status = content_status

            context.date_status = _compare_dates(context)

            context.confidence = _compute_confidence(
                evidence_score, contradiction, contradiction_override, thresholds
            )
            context.reasoning = self._build_reasoning(context, evidence_score)

            logger.info(
                "s11_verdict",
                source_status=context.source_status.value,
                content_status=content_status.value,
                date_status=context.date_status.value if context.date_status else None,
                confidence=context.confidence,
                evidence_score=round(evidence_score, 3),
                manipulation=manipulation.any_manipulation_detected,
            )
            return context

        except Exception as exc:
            raise ClassificationError(
                stage_id=self.stage_id.value,
                message=f"Classification failed: {exc}",
            ) from exc

    def _set_not_found(
        self,
        context: PipelineContext,
        *,
        reason: str,
        sem_sim: float | None = None,
    ) -> None:
        context.source_status = SourceStatus.NOT_FOUND
        context.content_status = None
        context.date_status = None

        source = context.normalized_source or context.raw_claimed_source

        if reason == "no_evidence":
            queries_tried = len(context.search_queries)
            context.confidence = 0.95
            context.reasoning = (
                f"No article matching the claim headline was found on {source or 'the claimed source'} "
                f"after executing {queries_tried} search query variant(s) across multiple providers. "
                "Verdict: source NOT_FOUND."
            )
        else:
            # Confidence rises the further below the gate the similarity sits.
            gate = _SETTINGS.classification.not_found_max_semantic_similarity
            raw_conf = 0.5 + (gate - (sem_sim or 0.0)) * 2
            context.confidence = round(max(0.55, min(0.90, raw_conf)), 3)
            context.reasoning = (
                f"An article was retrieved from {source or 'the claimed source'}, "
                f"but its semantic similarity to the claim is too low ({(sem_sim or 0.0):.2f}), "
                "indicating the retrieved article is unrelated to the claim. "
                "Verdict: source NOT_FOUND."
            )

        logger.info(
            "s11_verdict",
            source_status=context.source_status.value,
            content_status=None,
            date_status=None,
            confidence=context.confidence,
            reason=reason,
            sem_sim=round(sem_sim, 3) if sem_sim is not None else None,
        )

    def _build_reasoning(
        self,
        context: PipelineContext,
        evidence_score: float,
    ) -> str:
        parts: list[str] = []
        scores = context.scores
        article = context.top_article
        source = context.normalized_source or context.raw_claimed_source
        flags = context.manipulation_flags

        if article:
            parts.append(
                f"A matching article was found on {source or 'the claimed source'}."
            )

        if scores.semantic_similarity is not None:
            parts.append(f"Semantic similarity: {scores.semantic_similarity:.2f}.")
        if scores.entity_match is not None:
            parts.append(f"Entity match: {scores.entity_match:.2f}.")

        if scores.keyword_overlap is not None:
            kw_note = f"Keyword overlap: {scores.keyword_overlap:.2f}"

            if (
                scores.semantic_similarity is not None
                and abs(scores.keyword_overlap - scores.semantic_similarity) > 0.25
            ):
                if scores.keyword_overlap > scores.semantic_similarity:
                    kw_note += " (topic matches but content differs significantly)"
                else:
                    kw_note += " (similar language but different topic focus)"
            kw_note += "."
            parts.append(kw_note)

        if (
            scores.numerical_consistency is not None
            and scores.numerical_consistency < 1.0
        ):
            parts.append(
                f"Numerical consistency: {scores.numerical_consistency:.2f} "
                "(some numbers may differ)."
            )
        if scores.contradiction_score is not None and scores.contradiction_score > 0.3:
            parts.append(
                f"Contradiction detected (score: {scores.contradiction_score:.2f})."
            )

        if flags.headline_manipulated:
            parts.append(
                "Headline appears to have been manipulated relative to the original article."
            )
        if flags.body_altered:
            parts.append(
                "Article body shows significant divergence from the matched article."
            )
        if flags.numbers_altered:
            parts.append("One or more numerical values appear to have been altered.")
        if flags.entities_replaced:
            parts.append(
                "Named entities (persons/places/organisations) may have been substituted."
            )

        date_note = (
            {
                DateStatus.MATCHED: "The claimed publication date matches the source.",
                DateStatus.MISMATCHED: (
                    "The claimed publication date does not match the source's actual "
                    "publication date — this does not affect whether the content itself matches."
                ),
            }.get(context.date_status)
            if context.date_status
            else None
        )
        if date_note:
            parts.append(date_note)

        source_status = context.source_status.value if context.source_status else "UNKNOWN"
        content_status = context.content_status.value if context.content_status else "N/A"
        date_status = context.date_status.value if context.date_status else "UNKNOWN"
        verdict_line = f"Verdict: source {source_status}, content {content_status}, date {date_status}."
        parts.append(verdict_line)

        return " ".join(p for p in parts if p)


def _compare_dates(context: PipelineContext) -> DateStatus | None:
    claimed = context.published_date
    article = context.top_article
    actual = article.published_date if article else None

    if claimed is None or actual is None:
        return None

    return DateStatus.MATCHED if claimed == actual else DateStatus.MISMATCHED


def _compute_weighted_score(scores, thresholds) -> float:
    max_dim_weight = thresholds.max_single_dimension_weight

    dim_weights: list[tuple[float | None, float]] = [
        (scores.semantic_similarity, _W_SEM),
        (scores.entity_match, _W_ENT),
        (scores.keyword_overlap, _W_KW),
        (scores.numerical_consistency, _W_NUM),
    ]

    available: list[tuple[float, float]] = [
        (val, wt) for val, wt in dim_weights if val is not None
    ]

    if not available:
        return 0.0

    total_weight = sum(wt for _, wt in available)
    if total_weight == 0:
        return 0.0

    capped_available: list[tuple[float, float]] = []
    excess = 0.0
    uncapped_weight = 0.0

    for val, wt in available:
        effective = wt / total_weight
        if effective > max_dim_weight:
            excess += effective - max_dim_weight
            capped_available.append((val, max_dim_weight))
        else:
            capped_available.append((val, effective))
            uncapped_weight += effective

    if excess > 0 and uncapped_weight > 0:
        final: list[tuple[float, float]] = []
        for val, eff_wt in capped_available:
            if eff_wt < max_dim_weight and uncapped_weight > 0:
                redistribution = excess * (eff_wt / uncapped_weight)
                final.append((val, eff_wt + redistribution))
            else:
                final.append((val, eff_wt))
    else:
        final = capped_available

    result = sum(val * eff_wt for val, eff_wt in final)

    if len(available) < 4:
        logger.debug(
            "s11_weight_redistribution",
            available_dims=len(available),
            effective_weights={
                f"dim_{i}": round(eff_wt, 3) for i, (_, eff_wt) in enumerate(final)
            },
        )

    return max(0.0, min(1.0, result))


def _assign_content_status(
    evidence_score: float,
    manipulation,
    contradiction_override: bool,
    thresholds,
) -> ContentStatus:
    """MATCHED requires strong evidence AND no sign of alteration.

    Outright contradiction (contradiction_override) and detected manipulation
    both fall through to ALTERED regardless of the raw evidence score — a
    headline can score well on similarity while still being a manipulated
    version of the source article.
    """
    if contradiction_override:
        return ContentStatus.ALTERED

    if manipulation.any_manipulation_detected:
        return ContentStatus.ALTERED

    soft_true_threshold = (
        thresholds.partial_threshold + thresholds.true_threshold
    ) / 2.0

    if evidence_score >= soft_true_threshold:
        return ContentStatus.MATCHED

    return ContentStatus.ALTERED


def _compute_confidence(
    evidence_score: float,
    contradiction: float,
    contradiction_override: bool,
    thresholds,
) -> float:
    if contradiction_override:
        return round(min(0.95, 0.6 + contradiction * 0.35), 3)

    soft_true_threshold = (
        thresholds.partial_threshold + thresholds.true_threshold
    ) / 2.0
    distance = abs(evidence_score - soft_true_threshold)

    base = 0.5 + 0.47 * (1.0 - math.exp(-15.0 * distance))
    return round(min(0.97, max(0.50, base)), 3)
