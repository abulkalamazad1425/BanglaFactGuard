
from __future__ import annotations

import asyncio

import structlog

from app.core.constants import PipelineStageID
from app.features.verification.pipeline.context import PipelineContext
from app.features.nlp.embedding_service import EmbeddingService
from app.features.nlp.ner_service import NERService
from app.shared.utils.keyword_extractor import (
    compute_weighted_keyword_overlap,
    extract_keywords_with_scores,
    extract_headline_keywords,
)
from app.shared.utils.number_extractor import extract_numerals_set

logger = structlog.get_logger(__name__)




_ARTICLE_EXTRA_ENTITY_PENALTY = 0.3




_NUM_NEAR_MATCH_TOLERANCE = 0.10
_NUM_NEAR_MATCH_CREDIT = 0.5


class SimilarityAnalyzerStage:

    stage_id = PipelineStageID.S08_SIMILARITY_ANALYZER

    def __init__(
        self,
        embedding_service: EmbeddingService,
        ner_service: NERService,
    ) -> None:
        self._embedder = embedding_service
        self._ner = ner_service

    async def execute(self, context: PipelineContext) -> PipelineContext:
        if not context.top_article:
            logger.debug("s08_no_top_article_skipping")
            context.record_stage_error(self.stage_id, "No ranked article available for analysis")
            return context

        article = context.top_article
        claim_headline = context.normalized_headline
        claim_body = context.normalized_body or ""
        article_title = article.title or ""
        article_body = article.body or ""


        claim_full = f"{claim_headline} {claim_body}".strip()
        article_full = f"{article_title} {article_body}".strip()












        headline_sim: float | None = None
        body_sim: float | None = None
        sem_sim: float | None = None

        try:

            headline_sim_task = self._embedder.compute_similarity(
                claim_headline, article_title
            ) if article_title else asyncio.coroutine(lambda: 0.5)()

            body_sim_task = self._embedder.compute_similarity(
                claim_full, article_body
            ) if article_body else asyncio.coroutine(lambda: None)()

            headline_sim, body_sim = await asyncio.gather(
                headline_sim_task, body_sim_task
            )


            if body_sim is not None and headline_sim is not None:
                sem_sim = 0.3 * headline_sim + 0.7 * body_sim
            elif body_sim is not None:
                sem_sim = body_sim
            elif headline_sim is not None:
                sem_sim = headline_sim

            logger.debug(
                "s08_semantic_similarity",
                headline_sim=round(headline_sim, 4) if headline_sim is not None else None,
                body_sim=round(body_sim, 4) if body_sim is not None else None,
                composite=round(sem_sim, 4) if sem_sim is not None else None,
            )
        except Exception as exc:
            logger.warning("s08_semantic_similarity_failed", error=str(exc))
            context.record_stage_error(self.stage_id, f"Semantic similarity failed: {exc}")













        entity_match: float | None = None
        try:

            (claim_entities, article_entities,
             claim_typed, article_typed) = await _gather_entities_with_types(
                self._ner, claim_full, article_full
            )

            context.claim_entities = claim_entities
            context.article_entities = article_entities
            context.claim_entity_types = claim_typed
            context.article_entity_types = article_typed

            entity_match = _compute_directional_entity_overlap(
                claim_entities, article_entities
            )
            logger.debug(
                "s08_entity_match",
                score=round(entity_match, 4),
                claim_count=len(claim_entities),
                article_count=len(article_entities),
            )
        except Exception as exc:
            logger.warning("s08_entity_match_failed", error=str(exc))
            context.record_stage_error(self.stage_id, f"Entity match failed: {exc}")









        kw_overlap: float | None = None
        try:
            claim_kws_weighted = extract_keywords_with_scores(
                claim_headline, max_ngram_size=1, num_keywords=6
            )
            article_kws_weighted = extract_keywords_with_scores(
                article_full, max_ngram_size=2, num_keywords=10
            )

            context.claim_keywords = (
                context.claim_keywords
                or [kw for kw, _ in claim_kws_weighted]
            )
            kw_overlap = compute_weighted_keyword_overlap(
                claim_kws_weighted, article_kws_weighted
            )
            logger.debug("s08_keyword_overlap", score=round(kw_overlap, 4))
        except Exception as exc:
            logger.warning("s08_keyword_overlap_failed", error=str(exc))










        num_consistency: float | None = None
        try:
            claim_nums = extract_numerals_set(claim_full)
            article_nums = extract_numerals_set(article_full)
            context.claim_numerals = list(claim_nums)
            context.article_numerals = list(article_nums)
            num_consistency = _compute_asymmetric_numerical_consistency(
                claim_nums, article_nums
            )
            logger.debug("s08_numerical_consistency", score=round(num_consistency, 4))
        except Exception as exc:
            logger.warning("s08_numerical_consistency_failed", error=str(exc))




        context.update_scores(
            semantic_similarity=sem_sim,
            headline_similarity=headline_sim,
            body_similarity=body_sim,
            entity_match=entity_match,
            keyword_overlap=kw_overlap,
            numerical_consistency=num_consistency,
        )

        logger.info(
            "s08_analysis_complete",
            semantic=round(sem_sim, 3) if sem_sim is not None else None,
            headline_sim=round(headline_sim, 3) if headline_sim is not None else None,
            body_sim=round(body_sim, 3) if body_sim is not None else None,
            entity=round(entity_match, 3) if entity_match is not None else None,
            keyword=round(kw_overlap, 3) if kw_overlap is not None else None,
            numeral=round(num_consistency, 3) if num_consistency is not None else None,
        )
        return context







async def _gather_entities_with_types(
    ner: NERService, text_a: str, text_b: str
) -> tuple[list[str], list[str], list[tuple[str, str]], list[tuple[str, str]]]:
    results = await asyncio.gather(
        ner.extract_entities(text_a),
        ner.extract_entities(text_b),
        ner.extract_entities_with_types(text_a),
        ner.extract_entities_with_types(text_b),
    )
    return results[0], results[1], results[2], results[3]


def _compute_directional_entity_overlap(
    claim_entities: list[str],
    article_entities: list[str],
) -> float:
    if not claim_entities:
        return 1.0

    claim_set = {e.lower().strip() for e in claim_entities if e.strip()}
    article_set = {e.lower().strip() for e in article_entities if e.strip()}

    if not claim_set:
        return 1.0


    recall = len(claim_set & article_set) / len(claim_set)


    if article_set:
        extra_ratio = len(article_set - claim_set) / len(article_set)
        penalty = _ARTICLE_EXTRA_ENTITY_PENALTY * extra_ratio
    else:
        penalty = 0.0

    return max(0.0, min(1.0, recall - penalty))


def _compute_asymmetric_numerical_consistency(
    claim_nums: set[str],
    article_nums: set[str],
) -> float:
    if not claim_nums:
        return 1.0


    article_values: list[float] = []
    for n in article_nums:
        try:
            article_values.append(float(n.replace(",", "")))
        except ValueError:
            continue

    total_credit = 0.0
    for num_str in claim_nums:
        if num_str in article_nums:
            total_credit += 1.0
            continue


        try:
            claim_val = float(num_str.replace(",", ""))
        except ValueError:
            total_credit += 0.0
            continue

        near_match = any(
            abs(claim_val - av) <= _NUM_NEAR_MATCH_TOLERANCE * max(abs(claim_val), abs(av), 1e-9)
            for av in article_values
        )
        if near_match:
            total_credit += _NUM_NEAR_MATCH_CREDIT


    return total_credit / len(claim_nums)
