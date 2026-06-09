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
| body_altered        | Overall semantic similarity below body_altered threshold        |
| numbers_altered     | One or more claim numerals absent from article                  |
| entities_replaced   | One or more claim entities absent from article                  |

## Thresholds (runtime-configurable via AppSettings)

| Flag                | Threshold key                          | Default |
|---------------------|----------------------------------------|---------|
| headline_manipulated| HEADLINE_SIM_THRESHOLD / BODY_SIM_HIGH | 0.60/0.80|
| body_altered        | BODY_ALTERED_THRESHOLD                 | 0.55    |
| numbers_altered     | (any absent numeral)                   | n/a     |
| entities_replaced   | ENTITY_REPLACED_THRESHOLD              | < 0.5   |

## ManipulationType enum population

In addition to setting boolean flags on `ManipulationFlagsSchema`, this stage
also populates `context.detected_manipulations` as a list of `ManipulationType`
enums for the reasoning builder in Stage 11.

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
from app.shared.utils.number_extractor import find_altered_numbers

logger = structlog.get_logger(__name__)
_SETTINGS = get_settings()


class ManipulationDetectorStage:
    """
    Stage 10: Detect headline manipulation, body alteration, numerical changes,
    and entity substitution.

    Dependencies:
        embedding_service: For headline-vs-headline similarity check.
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
        # ------------------------------------------------------------------
        try:
            headline_sim = await self._compute_headline_similarity(context, article)
            body_sim = scores.semantic_similarity or 0.0

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
        # 2. Body alteration detection
        # ------------------------------------------------------------------
        body_sim = scores.semantic_similarity
        if body_sim is not None and body_sim < self._thresholds.body_altered_threshold:
            flags = ManipulationFlagsSchema(
                **{**flags.model_dump(), "body_altered": True}
            )
            detected.append(ManipulationType.BODY_ALTERED)
            logger.info("s10_body_alteration_detected", semantic_sim=round(body_sim, 3))

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
        # 4. Entity replacement detection
        # ------------------------------------------------------------------
        entity_score = scores.entity_match
        if (
            entity_score is not None
            and entity_score < self._thresholds.entity_replaced_threshold
            and context.claim_entities  # Only flag if claim actually has entities
        ):
            flags = ManipulationFlagsSchema(
                **{**flags.model_dump(), "entities_replaced": True}
            )
            detected.append(ManipulationType.ENTITIES_REPLACED)
            logger.info(
                "s10_entities_replaced_detected",
                entity_score=round(entity_score, 3),
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

        Uses only titles (not full text) to isolate headline-level manipulation.

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

