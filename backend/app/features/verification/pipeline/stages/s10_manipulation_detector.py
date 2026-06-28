"""
app/pipelines/stages/s10_manipulation_detector.py
===================================================
Stage 10: Manipulation Detection

## Responsibility

Detect specific types of content manipulation by comparing the claim against
the best-matching article across four independent detectors:

| Flag                | Trigger condition                                               |
|---------------------|-----------------------------------------------------------------|
| headline_manipulated| Headline similarity LOW but body similarity HIGH                |
| body_altered        | Semantic similarity LOW but keyword overlap MODERATE+           |
| numbers_altered     | One or more claim numerals absent from article                  |
| entities_replaced   | Entity overlap LOW + same-type substitution detected            |

## Thresholds (runtime-configurable via AppSettings)

| Flag                | Threshold key                          | Default |
|---------------------|----------------------------------------|---------|
| headline_manipulated| HEADLINE_SIM_THRESHOLD / BODY_SIM_HIGH | 0.55/0.75|
| body_altered        | BODY_ALTERED_THRESHOLD + MIN_KW_OVERLAP| 0.50/0.30|
| numbers_altered     | (any absent numeral)                   | n/a     |
| entities_replaced   | ENTITY_REPLACED_THRESHOLD              | < 0.45  |

## Improvement notes (v2)

1. **Pre-computed headline similarity**: Reads `context.scores.headline_similarity`
   from S08 instead of making a redundant LaBSE call. Falls back to the old
   `_compute_headline_similarity` only if the pre-computed value is None.

2. **Fabricated content detection**: If BOTH headline and body similarity are
   low, the content is likely fabricated (not just headline-swapped). This
   case was previously missed — now triggers body_altered.

3. **Refined body_altered**: Only fires when semantic similarity is low AND
   keyword overlap is moderately high (≥ 0.30). This distinguishes "wrong
   article retrieved" (low everything) from "article body was altered"
   (topic matches but content differs).

4. **Entity-type-aware substitution**: Uses typed NER entities from S08 to
   detect same-type substitution (e.g. PER→PER, LOC→LOC). This is a
   stronger signal of deliberate manipulation than raw entity overlap alone.

## Criticality: NON-CRITICAL
All flags default to False on any failure — the pipeline continues without
manipulation detection rather than blocking the classification.
"""

from __future__ import annotations

import structlog

from app.core.config import get_settings
from app.core.constants import ManipulationType, PipelineStageID
from app.features.verification.pipeline.context import PipelineContext
from app.features.verification.schemas import ManipulationFlagsSchema
from app.features.nlp.embedding_service import EmbeddingService
from app.features.nlp.ner_service import NERService
from app.shared.utils.number_extractor import find_altered_numbers

logger = structlog.get_logger(__name__)
_SETTINGS = get_settings()


class ManipulationDetectorStage:
    """
    Stage 10: Detect headline manipulation, body alteration, numerical changes,
    and entity substitution.

    Dependencies:
        embedding_service: For headline-vs-headline similarity check (fallback only).
    """

    stage_id = PipelineStageID.S10_MANIPULATION_DETECTOR

    def __init__(self, embedding_service: EmbeddingService) -> None:
        self._embedder = embedding_service
        self._thresholds = _SETTINGS.classification

    async def execute(self, context: PipelineContext) -> PipelineContext:
        """
        Run all four manipulation detectors and populate context flags.

        Args:
            context: Pipeline context with scores, top_article, claim_entities,
                     claim_numerals, article_entities, article_numerals set.

        Returns:
            Context with manipulation_flags and detected_manipulations populated.
        """
        if not context.top_article:
            logger.debug("s10_no_top_article_skipping")
            return context

        flags = ManipulationFlagsSchema()
        detected: list[ManipulationType] = []

        article = context.top_article
        scores = context.scores

        # ------------------------------------------------------------------
        # 1. Headline manipulation detection
        #
        #    Uses the pre-computed headline_similarity from S08 (eliminates
        #    the previous redundant LaBSE call). Falls back to computing
        #    it directly only if S08 didn't produce a value.
        #
        #    Trigger: headline similarity is LOW but body similarity is HIGH.
        #    This pattern indicates the headline was swapped/altered while
        #    the article body remains largely the same — a common
        #    misinformation technique (clickbait / misleading headline).
        # ------------------------------------------------------------------
        try:
            # Prefer pre-computed value from S08 to avoid duplicate inference
            headline_sim = scores.headline_similarity
            if headline_sim is None:
                headline_sim = await self._compute_headline_similarity(context, article)

            # Use body_similarity if available, fall back to semantic_similarity
            body_sim = scores.body_similarity or scores.semantic_similarity or 0.0

            if (
                headline_sim < self._thresholds.headline_sim_threshold
                and body_sim >= self._thresholds.body_sim_high
            ):
                flags = ManipulationFlagsSchema(
                    **{**flags.model_dump(), "headline_manipulated": True}
                )
                detected.append(ManipulationType.HEADLINE_MANIPULATED)
                logger.info(
                    "s10_headline_manipulation_detected",
                    headline_sim=round(headline_sim, 3),
                    body_sim=round(body_sim, 3),
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("s10_headline_check_failed", error=str(exc))

        # ------------------------------------------------------------------
        # 2. Body alteration detection (refined)
        #
        #    Previous logic: fire when semantic_similarity < threshold.
        #    Problem: this overlaps with the FALSE verdict in S11 and doesn't
        #    distinguish "wrong article retrieved" from "body was altered".
        #
        #    New logic: fire ONLY when semantic_similarity is low AND
        #    keyword_overlap is moderately high. This means the topic matches
        #    (keywords overlap) but the actual content differs (semantic sim
        #    is low) — a strong signal that the body was rewritten or altered
        #    while preserving the general topic.
        #
        #    Also detect fabricated content: if BOTH headline AND body
        #    similarity are low, the entire content was likely fabricated.
        # ------------------------------------------------------------------
        sem_sim = scores.semantic_similarity
        kw_overlap = scores.keyword_overlap
        headline_sim_val = scores.headline_similarity

        if sem_sim is not None and sem_sim < self._thresholds.body_altered_threshold:
            # Check if this is "altered body" (topic matches) vs "wrong article"
            if kw_overlap is not None and kw_overlap >= self._thresholds.body_altered_min_keyword_overlap:
                # Topic matches but content differs → body was altered
                flags = ManipulationFlagsSchema(
                    **{**flags.model_dump(), "body_altered": True}
                )
                detected.append(ManipulationType.BODY_ALTERED)
                logger.info(
                    "s10_body_alteration_detected",
                    semantic_sim=round(sem_sim, 3),
                    keyword_overlap=round(kw_overlap, 3),
                    reason="topic_match_content_mismatch",
                )
            elif (
                headline_sim_val is not None
                and headline_sim_val < self._thresholds.headline_sim_threshold
            ):
                # Both headline AND body similarity are low → fabricated content.
                # This case was previously missed by the old logic which only
                # detected body alteration OR headline swapping, not both low.
                flags = ManipulationFlagsSchema(
                    **{**flags.model_dump(), "body_altered": True}
                )
                detected.append(ManipulationType.BODY_ALTERED)
                logger.info(
                    "s10_fabricated_content_detected",
                    semantic_sim=round(sem_sim, 3),
                    headline_sim=round(headline_sim_val, 3),
                    reason="both_headline_and_body_low",
                )

        # ------------------------------------------------------------------
        # 3. Numerical alteration detection
        # ------------------------------------------------------------------
        try:
            claim_full = f"{context.normalized_headline} {context.normalized_body or ''}"
            article_full = f"{article.title or ''} {article.body or ''}"
            altered_nums = find_altered_numbers(claim_full, article_full)
            if altered_nums:
                flags = ManipulationFlagsSchema(
                    **{**flags.model_dump(), "numbers_altered": True}
                )
                detected.append(ManipulationType.NUMBERS_ALTERED)
                logger.info(
                    "s10_numbers_altered_detected",
                    altered_count=len(altered_nums),
                    examples=str(altered_nums[:3]),
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("s10_number_check_failed", error=str(exc))

        # ------------------------------------------------------------------
        # 4. Entity replacement detection (type-aware)
        #
        #    Two complementary checks:
        #    a) Raw entity overlap score below threshold (existing check).
        #    b) Same-type substitution detected via typed NER (new check).
        #
        #    Same-type substitution (e.g. one person's name replaced with
        #    another) is a stronger signal of deliberate manipulation than
        #    simple entity mismatch, which may just indicate topic difference.
        # ------------------------------------------------------------------
        entity_score = scores.entity_match
        entity_flagged = False

        # Check raw overlap score
        if (
            entity_score is not None
            and entity_score < self._thresholds.entity_replaced_threshold
            and context.claim_entities  # Only flag if claim actually has entities
        ):
            entity_flagged = True

        # Check same-type substitution (PER→PER, LOC→LOC, ORG→ORG)
        # This catches cases where entity overlap is low AND the specific types
        # that differ match — a hallmark of deliberate entity substitution.
        if (
            not entity_flagged
            and context.claim_entity_types
            and context.article_entity_types
        ):
            type_substitution = NERService.compute_typed_entity_substitution(
                context.claim_entity_types,
                context.article_entity_types,
            )
            if type_substitution:
                entity_flagged = True
                logger.debug("s10_same_type_entity_substitution_detected")

        if entity_flagged:
            flags = ManipulationFlagsSchema(
                **{**flags.model_dump(), "entities_replaced": True}
            )
            detected.append(ManipulationType.ENTITIES_REPLACED)
            logger.info(
                "s10_entities_replaced_detected",
                entity_score=round(entity_score, 3) if entity_score is not None else None,
                claim_entities=context.claim_entities[:5],
            )

        context.manipulation_flags = flags
        context.detected_manipulations = detected

        logger.info(
            "s10_detection_complete",
            any_manipulation=flags.any_manipulation_detected,
            flags=flags.model_dump(),
        )
        return context

    async def _compute_headline_similarity(self, context: PipelineContext, article) -> float:
        """
        Compute LaBSE similarity between claim headline and article title.

        Fallback method — only used if S08 didn't pre-compute headline_similarity.

        Args:
            context: Pipeline context with normalized_headline.
            article: The top-ranked RankedArticleSchema.

        Returns:
            Cosine similarity in [0.0, 1.0]. Returns 0.5 if no article title.
        """
        article_title = article.title or ""
        if not article_title:
            return 0.5  # Unknown — neutral

        return await self._embedder.compute_similarity(
            context.normalized_headline,
            article_title,
        )
