"""
app/pipelines/stages/s08_similarity_analyzer.py
==================================================
Stage 8: Multi-Dimensional Similarity Analysis

## Responsibility

Compute four similarity dimensions between the claim and the top-ranked article:

| Dimension              | Method                          | Score |
|------------------------|---------------------------------|-------|
| semantic_similarity    | LaBSE cosine (claim vs article) | [0,1] |
| entity_match           | NER set-intersection ratio      | [0,1] |
| keyword_overlap        | Jaccard of keyword sets         | [0,1] |
| numerical_consistency  | Numeral intersection ratio      | [0,1] |

`contradiction_score` is left as None here — it is populated in Stage 9 (NLI).

## Criticality: NON-CRITICAL
Each dimension is computed independently. Failure in one dimension
leaves its score as None; the classifier handles None scores.
"""

from __future__ import annotations

import structlog

from app.core.constants import PipelineStageID
from app.features.verification.pipeline.context import PipelineContext
from app.features.nlp.embedding_service import EmbeddingService
from app.features.nlp.ner_service import NERService
from app.shared.utils.keyword_extractor import compute_keyword_overlap, extract_body_keywords, extract_headline_keywords
from app.shared.utils.number_extractor import compute_numerical_consistency, extract_numerals

logger = structlog.get_logger(__name__)


class SimilarityAnalyzerStage:
    """
    Stage 8: Compute semantic similarity, entity match, keyword overlap,
    and numerical consistency between claim and best evidence article.

    Dependencies:
        embedding_service: LaBSE for semantic similarity.
        ner_service:       BanglaBERT NER for entity extraction.
    """

    stage_id = PipelineStageID.S08_SIMILARITY_ANALYZER

    def __init__(
        self,
        embedding_service: EmbeddingService,
        ner_service: NERService,
    ) -> None:
        self._embedder = embedding_service
        self._ner = ner_service

    async def execute(self, context: PipelineContext) -> PipelineContext:
        """
        Compute all four similarity dimensions and store in context.scores.

        Args:
            context: Pipeline context with top_article and normalized_headline set.

        Returns:
            Context with scores.semantic_similarity, scores.entity_match,
            scores.keyword_overlap, and scores.numerical_consistency populated.
        """
        if not context.top_article:
            logger.debug("s08_no_top_article_skipping")
            context.record_stage_error(self.stage_id, "No ranked article available for analysis")
            return context

        article = context.top_article
        claim_headline = context.normalized_headline
        claim_body = context.normalized_body or ""
        article_title = article.title or ""
        article_body = article.body or ""

        # Full claim text for multi-field analysis
        claim_full = f"{claim_headline} {claim_body}".strip()
        article_full = f"{article_title} {article_body}".strip()

        # ------------------------------------------------------------------
        # 1. Semantic similarity (LaBSE: claim full text vs article full text)
        # ------------------------------------------------------------------
        sem_sim: float | None = None
        try:
            sem_sim = await self._embedder.compute_similarity(claim_full, article_full)
            logger.debug("s08_semantic_similarity", score=round(sem_sim, 4))
        except Exception as exc:  # noqa: BLE001
            logger.warning("s08_semantic_similarity_failed", error=str(exc))
            context.record_stage_error(self.stage_id, f"Semantic similarity failed: {exc}")

        # ------------------------------------------------------------------
        # 2. Entity match (BanglaBERT NER on both texts)
        # ------------------------------------------------------------------
        entity_match: float | None = None
        try:
            claim_entities, article_entities = await _gather_entities(
                self._ner, claim_full, article_full
            )
            context.claim_entities = claim_entities
            context.article_entities = article_entities
            entity_match = self._ner.compute_entity_overlap(claim_entities, article_entities)
            logger.debug(
                "s08_entity_match",
                score=round(entity_match, 4),
                claim_entity_count=len(claim_entities),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("s08_entity_match_failed", error=str(exc))
            context.record_stage_error(self.stage_id, f"Entity match failed: {exc}")

        # ------------------------------------------------------------------
        # 3. Keyword overlap (YAKE Jaccard)
        # ------------------------------------------------------------------
        kw_overlap: float | None = None
        try:
            claim_kws = (
                context.claim_keywords
                or extract_headline_keywords(claim_headline)
            )
            article_kws = extract_body_keywords(article_full, top_n=10)
            context.claim_keywords = claim_kws
            kw_overlap = compute_keyword_overlap(claim_kws, article_kws)
            logger.debug("s08_keyword_overlap", score=round(kw_overlap, 4))
        except Exception as exc:  # noqa: BLE001
            logger.warning("s08_keyword_overlap_failed", error=str(exc))

        # ------------------------------------------------------------------
        # 4. Numerical consistency
        # ------------------------------------------------------------------
        num_consistency: float | None = None
        try:
            context.claim_numerals = extract_numerals(claim_full)
            context.article_numerals = extract_numerals(article_full)
            num_consistency = compute_numerical_consistency(claim_full, article_full)
            logger.debug("s08_numerical_consistency", score=round(num_consistency, 4))
        except Exception as exc:  # noqa: BLE001
            logger.warning("s08_numerical_consistency_failed", error=str(exc))

        # ------------------------------------------------------------------
        # Update context scores (merge — preserves existing values)
        # ------------------------------------------------------------------
        context.update_scores(
            semantic_similarity=sem_sim,
            entity_match=entity_match,
            keyword_overlap=kw_overlap,
            numerical_consistency=num_consistency,
        )

        logger.info(
            "s08_analysis_complete",
            semantic=round(sem_sim, 3) if sem_sim is not None else None,
            entity=round(entity_match, 3) if entity_match is not None else None,
            keyword=round(kw_overlap, 3) if kw_overlap is not None else None,
            numeral=round(num_consistency, 3) if num_consistency is not None else None,
        )
        return context


async def _gather_entities(
    ner: NERService, text_a: str, text_b: str
) -> tuple[list[str], list[str]]:
    """Run NER on both texts concurrently."""
    import asyncio
    return await asyncio.gather(
        ner.extract_entities(text_a),
        ner.extract_entities(text_b),
    )

