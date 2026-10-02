from __future__ import annotations

import structlog

from app.core.constants import CheckState, ClaimScope, ManipulationType, PipelineStageID
from app.features.verification.analysis.discrepancies import (
    ALIGN_MIN_STRENGTH,
    EvidenceSentence,
    analyze,
    sentences_of,
)
from app.features.verification.analysis.text import split_sentences
from app.features.verification.pipeline.context import PipelineContext
from app.features.verification.schemas import (
    AlteredNumberDetail,
    DiscrepancyDetail,
    ManipulationFlagsSchema,
    SubstitutedEntityDetail,
)

logger = structlog.get_logger(__name__)

# Fraction of submitted-body sentences that must find an aligned source
# sentence before the body check can claim to have evaluated the body.
_BODY_MIN_ALIGNED_FRACTION = 0.5


class ManipulationDetectorStage:
    """Concrete, evidence-backed alteration checks — scope-aware.

    A flag is set ONLY when a specific discrepancy between the claim and the
    source sentence discussing the same thing is found (changed number or
    unit, flipped negation, same-type-same-role entity substitution, role
    swap, scope/quantifier change, changed attribution, plan-vs-completed).
    Low similarity or low entity coverage alone never sets a flag: those are
    measurements, handled (as "not established") by S11.

    Every check ends in an explicit state: PASSED / FAILED / NOT_EVALUATED /
    NOT_APPLICABLE. For photo cards (HEADLINE_ONLY) the submitted-body check
    is NOT_APPLICABLE and no body text — real or synthetic — takes part in any
    check.
    """

    stage_id = PipelineStageID.S10_MANIPULATION_DETECTOR

    def __init__(self, embedding_service=None) -> None:  # signature kept for the factory
        self._embedder = embedding_service

    async def execute(self, context: PipelineContext) -> PipelineContext:
        if not context.top_article:
            logger.debug("s10_no_top_article_skipping")
            return context

        article = context.top_article
        with_body = context.claim_scope == ClaimScope.HEADLINE_WITH_BODY and context.has_body

        claim_sentences = sentences_of(context.normalized_headline, "headline")
        if with_body and context.normalized_body:
            claim_sentences += sentences_of(context.normalized_body, "body")

        evidence = [EvidenceSentence(article.title, "title")] if article.title else []
        evidence += [
            EvidenceSentence(s, "body") for s in split_sentences(article.body or "", min_len=10)
        ]

        try:
            results, alignments = analyze(
                claim_sentences,
                evidence,
                context.claim_mentions,
                context.evidence_mentions,
                ner_available=context.ner_available,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("s10_checks_failed", error=str(exc))
            context.record_stage_error(self.stage_id, f"Alteration checks failed: {exc}")
            return context

        discrepancies = [d for r in results.values() for d in r.discrepancies]
        states: dict[str, CheckState] = {name: r.state for name, r in results.items()}

        # Per-part states derived from the sentence alignments.
        head_al = [a for a in alignments if a.claim.part == "headline"]
        body_al = [a for a in alignments if a.claim.part == "body"]
        head_failed = any(d.part == "headline" for d in discrepancies)
        body_failed = any(d.part == "body" for d in discrepancies)

        if head_failed:
            states["headline"] = CheckState.FAILED
        elif head_al and all(a.aligned for a in head_al):
            states["headline"] = CheckState.PASSED
        else:
            states["headline"] = CheckState.NOT_EVALUATED

        if not with_body:
            states["body"] = CheckState.NOT_APPLICABLE
        elif body_failed:
            states["body"] = CheckState.FAILED
        elif body_al and sum(a.aligned for a in body_al) / len(body_al) >= _BODY_MIN_ALIGNED_FRACTION:
            states["body"] = CheckState.PASSED
        else:
            states["body"] = CheckState.NOT_EVALUATED

        altered_numbers = [
            AlteredNumberDetail(
                claimed=d.meta.get("claimed", ""), nearest_in_article=d.meta.get("source")
            )
            for d in discrepancies
            if d.kind == "numbers"
        ]
        substituted = [
            SubstitutedEntityDetail(
                entity_type=d.meta.get("type", ""),
                claimed=[d.meta.get("claimed", "")],
                article_same_type=[d.meta.get("source", "")],
            )
            for d in discrepancies
            if d.kind == "entity_substitution"
        ]

        flags = ManipulationFlagsSchema(
            headline_manipulated=head_failed,
            body_altered=body_failed and with_body,
            numbers_altered=states.get("numbers") == CheckState.FAILED,
            entities_replaced=states.get("entities") == CheckState.FAILED,
            altered_numbers=altered_numbers,
            substituted_entities=substituted,
            check_states=states,
            discrepancies=[
                DiscrepancyDetail(
                    kind=d.kind,
                    claim_text=d.claim_text,
                    evidence_text=d.evidence_text,
                    detail=d.detail,
                    part=d.part,
                )
                for d in discrepancies
            ],
        )
        detected: list[ManipulationType] = []
        if flags.headline_manipulated:
            detected.append(ManipulationType.HEADLINE_MANIPULATED)
        if flags.body_altered:
            detected.append(ManipulationType.BODY_ALTERED)
        if flags.numbers_altered:
            detected.append(ManipulationType.NUMBERS_ALTERED)
        if flags.entities_replaced:
            detected.append(ManipulationType.ENTITIES_REPLACED)

        context.manipulation_flags = flags
        context.detected_manipulations = detected
        logger.info(
            "s10_detection_complete",
            scope=context.claim_scope.value,
            any_manipulation=flags.any_manipulation_detected,
            check_states={k: v.value for k, v in states.items()},
            discrepancy_kinds=[d.kind for d in discrepancies],
            align_min=ALIGN_MIN_STRENGTH,
        )
        return context
