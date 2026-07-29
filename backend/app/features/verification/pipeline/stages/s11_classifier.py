
from __future__ import annotations

import math

import structlog

from app.core.config import get_settings
from app.core.constants import ManipulationType, PipelineStageID, VerificationLabel
from app.core.exceptions import ClassificationError
from app.features.verification.pipeline.context import PipelineContext

logger = structlog.get_logger(__name__)
_SETTINGS = get_settings()


_W_SEM = 0.45
_W_ENT = 0.25
_W_KW = 0.15
_W_NUM = 0.15



assert abs((_W_SEM + _W_ENT + _W_KW + _W_NUM) - 1.0) < 1e-9, (
    f"Score aggregation weights must sum to 1.0, got {_W_SEM + _W_ENT + _W_KW + _W_NUM}"
)


class ClassifierStage:

    stage_id = PipelineStageID.S11_CLASSIFIER

    async def execute(self, context: PipelineContext) -> PipelineContext:
        thresholds = _SETTINGS.classification

        try:



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







            sem_sim = context.scores.semantic_similarity
            if (
                sem_sim is not None
                and sem_sim < thresholds.not_found_max_semantic_similarity
            ):



                raw_conf = 0.5 + (thresholds.not_found_max_semantic_similarity - sem_sim) * 2
                context.label = VerificationLabel.NOT_FOUND_IN_CLAIMED_SOURCE
                context.confidence = round(max(0.55, min(0.90, raw_conf)), 3)
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




            scores = context.scores
            evidence_score = _compute_weighted_score(scores, thresholds)


            contradiction = scores.contradiction_score or 0.0
            if contradiction > thresholds.contradiction_override_threshold:

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


            if contradiction > 0.5:
                penalty = (contradiction - 0.5) * 0.4
                evidence_score = max(0.0, evidence_score - penalty)


            if context.stage_error_count > 0:
                degradation = min(0.15, context.stage_error_count * 0.05)
                evidence_score = max(0.0, evidence_score - degradation)




            manipulation = context.manipulation_flags
            label = _assign_label(evidence_score, manipulation, thresholds)




            confidence = _compute_confidence(evidence_score, label, thresholds)




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





    def _build_reasoning(
        self,
        context: PipelineContext,
        label: VerificationLabel,
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
        else:
            parts.append(f"No matching article was found on {source or 'the claimed source'}.")


        if scores.semantic_similarity is not None:
            parts.append(
                f"Semantic similarity: {scores.semantic_similarity:.2f}."
            )
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

        if scores.numerical_consistency is not None and scores.numerical_consistency < 1.0:
            parts.append(
                f"Numerical consistency: {scores.numerical_consistency:.2f} "
                "(some numbers may differ)."
            )
        if scores.contradiction_score is not None and scores.contradiction_score > 0.3:
            parts.append(
                f"Contradiction detected (score: {scores.contradiction_score:.2f})."
            )


        if flags.headline_manipulated:
            parts.append("Headline appears to have been manipulated relative to the original article.")
        if flags.body_altered:
            parts.append("Article body shows significant divergence from the matched article.")
        if flags.numbers_altered:
            parts.append("One or more numerical values appear to have been altered.")
        if flags.entities_replaced:
            parts.append("Named entities (persons/places/organisations) may have been substituted.")


        label_summary = {
            VerificationLabel.TRUE: "Verdict: The claim is TRUE — the source published matching content.",
            VerificationLabel.FALSE: "Verdict: The claim is FALSE — the article contradicts or significantly differs.",
            VerificationLabel.PARTIALLY_TRUE: "Verdict: The claim is PARTIALLY TRUE — the source published related content with alterations.",
            VerificationLabel.NOT_FOUND_IN_CLAIMED_SOURCE: "Verdict: NOT FOUND IN CLAIMED SOURCE — no matching article was retrieved.",
        }
        parts.append(label_summary.get(label, ""))

        return " ".join(p for p in parts if p)

    def _build_not_found_reasoning(self, context: PipelineContext) -> str:
        source = context.normalized_source or context.raw_claimed_source
        queries_tried = len(context.search_queries)
        return (
            f"No article matching the claim headline was found on {source or 'the claimed source'} "
            f"after executing {queries_tried} search query variant(s) across multiple providers. "
            "Verdict: NOT FOUND IN CLAIMED SOURCE."
        )







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


def _assign_label(evidence_score: float, manipulation, thresholds) -> VerificationLabel:
    any_manip = manipulation.any_manipulation_detected

    if evidence_score >= thresholds.true_threshold:
        if any_manip:
            return VerificationLabel.PARTIALLY_TRUE
        return VerificationLabel.TRUE





    soft_true_threshold = (thresholds.partial_threshold + thresholds.true_threshold) / 2.0

    if evidence_score >= soft_true_threshold:
        if any_manip:
            return VerificationLabel.PARTIALLY_TRUE
        return VerificationLabel.TRUE

    if evidence_score >= thresholds.partial_threshold:
        return VerificationLabel.PARTIALLY_TRUE

    return VerificationLabel.FALSE


def _compute_confidence(
    evidence_score: float, label: VerificationLabel, thresholds
) -> float:

    boundaries = [
        thresholds.true_threshold,
        thresholds.partial_threshold,
        thresholds.false_threshold,
    ]
    min_distance = min(abs(evidence_score - b) for b in boundaries)




    base = 0.5 + 0.47 * (1.0 - math.exp(-15.0 * min_distance))
    confidence = round(min(0.97, max(0.50, base)), 3)
    return confidence
