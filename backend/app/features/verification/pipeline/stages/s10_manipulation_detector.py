
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

    stage_id = PipelineStageID.S10_MANIPULATION_DETECTOR

    def __init__(self, embedding_service: EmbeddingService) -> None:
        self._embedder = embedding_service
        self._thresholds = _SETTINGS.classification

    async def execute(self, context: PipelineContext) -> PipelineContext:
        if not context.top_article:
            logger.debug("s10_no_top_article_skipping")
            return context

        flags = ManipulationFlagsSchema()
        detected: list[ManipulationType] = []

        article = context.top_article
        scores = context.scores













        try:

            headline_sim = scores.headline_similarity
            if headline_sim is None:
                headline_sim = await self._compute_headline_similarity(context, article)


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
        except Exception as exc:
            logger.warning("s10_headline_check_failed", error=str(exc))

















        sem_sim = scores.semantic_similarity
        kw_overlap = scores.keyword_overlap
        headline_sim_val = scores.headline_similarity

        if sem_sim is not None and sem_sim < self._thresholds.body_altered_threshold:

            if kw_overlap is not None and kw_overlap >= self._thresholds.body_altered_min_keyword_overlap:

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
        except Exception as exc:
            logger.warning("s10_number_check_failed", error=str(exc))












        entity_score = scores.entity_match
        entity_flagged = False


        if (
            entity_score is not None
            and entity_score < self._thresholds.entity_replaced_threshold
            and context.claim_entities
        ):
            entity_flagged = True




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
        article_title = article.title or ""
        if not article_title:
            return 0.5

        return await self._embedder.compute_similarity(
            context.normalized_headline,
            article_title,
        )
