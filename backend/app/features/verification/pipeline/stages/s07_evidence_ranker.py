"""
app/pipelines/stages/s07_evidence_ranker.py
=============================================
Stage 7: Evidence Ranking

## Responsibility

Rank the extracted candidate articles (from Stage 6) by relevance to the claim,
and select the top-K as evidence for Stages 8–11.

## Ranking formula

Each article receives a composite rank_score from three components:

    rank_score = (
        W_SEM  * semantic_similarity   +  # LaBSE cosine sim of headlines
        W_KW   * keyword_overlap       +  # Jaccard of claim vs article keywords
        W_DATE * date_bonus            +  # 1.0 if dates match, else 0.0
    )

    Weights: W_SEM=0.60, W_KW=0.25, W_DATE=0.15

Semantic similarity (headline vs headline) is the dominant signal because
it captures topical equivalence across paraphrasing and transliteration.

Keyword overlap provides a fast, model-free complementary signal.

Date bonus rewards articles whose publication date matches the claimed date,
without penalising articles with unknown dates (date_bonus=0.5 when unknown).

## Top-K selection

After ranking, the list is sorted by rank_score DESC and truncated to
`max_ranked_articles` (from settings, default 5). Only articles above
a minimum rank threshold (`min_rank_score`, default 0.05) are kept.

The highest-ranked article is stored as `context.top_article`.

## Criticality: NON-CRITICAL
If ranking fails or all articles fall below the minimum threshold,
the original extraction order is preserved as a fallback.
"""

from __future__ import annotations

import structlog

from app.core.config import get_settings
from app.core.constants import PipelineStageID
from app.features.verification.pipeline.context import PipelineContext
from app.features.articles.schemas import RankedArticleSchema
from app.features.nlp.embedding_service import EmbeddingService
from app.shared.utils.keyword_extractor import compute_keyword_overlap, extract_headline_keywords

logger = structlog.get_logger(__name__)
_SETTINGS = get_settings()

_W_SEM = 0.60
_W_KW = 0.25
_W_DATE = 0.15


class EvidenceRankerStage:
    """
    Stage 7: Rank extracted articles by relevance using LaBSE + keyword overlap.

    Dependencies:
        embedding_service: For computing LaBSE headline similarity.
    """

    stage_id = PipelineStageID.S07_EVIDENCE_RANKER

    def __init__(self, embedding_service: EmbeddingService) -> None:
        self._embedder = embedding_service
        self._max_ranked = _SETTINGS.ml.max_ranked_articles
        self._min_score = _SETTINGS.ml.min_rank_score

    async def execute(self, context: PipelineContext) -> PipelineContext:
        """
        Compute rank scores for all extracted articles and select top-K.

        Args:
            context: Pipeline context with extracted_articles (Stage 6 output).

        Returns:
            Context with ranked_articles (sorted DESC) and top_article set.
        """
        articles = context.extracted_articles

        if not articles:
            logger.debug("s07_no_articles_to_rank")
            context.ranked_articles = []
            context.top_article = None
            return context

        claim_headline = context.normalized_headline
        claim_keywords = context.claim_keywords or extract_headline_keywords(claim_headline)

        scored: list[tuple[float, RankedArticleSchema]] = []

        for article in articles:
            score = await self._score_article(
                article=article,
                claim_headline=claim_headline,
                claim_keywords=claim_keywords,
                claim_date=context.published_date,
            )
            scored.append((score, article))

        # Sort by score descending
        scored.sort(key=lambda x: x[0], reverse=True)

        # Filter below minimum threshold, then take top-K
        ranked: list[RankedArticleSchema] = []
        for score, article in scored:
            if score < self._min_score:
                break
            # Rebuild schema with updated rank_score
            updated = RankedArticleSchema(
                url=article.url,
                title=article.title,
                body=article.body,
                author=article.author,
                published_date=article.published_date,
                rank_score=round(score, 4),
                search_provider=article.search_provider,
                extraction_method=article.extraction_method,
            )
            ranked.append(updated)
            if len(ranked) >= self._max_ranked:
                break

        # Fallback: if all below threshold, keep top-1 anyway
        if not ranked and scored:
            best_score, best_article = scored[0]
            ranked = [
                RankedArticleSchema(
                    **{**best_article.model_dump(), "rank_score": round(best_score, 4)}
                )
            ]

        context.ranked_articles = ranked
        context.top_article = ranked[0] if ranked else None

        logger.info(
            "s07_ranking_complete",
            total_extracted=len(articles),
            ranked_count=len(ranked),
            top_score=ranked[0].rank_score if ranked else 0.0,
        )
        return context

    async def _score_article(
        self,
        article: RankedArticleSchema,
        claim_headline: str,
        claim_keywords: list[str],
        claim_date,
    ) -> float:
        """
        Compute the composite rank score for a single article.

        Args:
            article:         The candidate article to score.
            claim_headline:  Normalised claim headline.
            claim_keywords:  Pre-extracted claim keywords.
            claim_date:      Claimed publication date (may be None).

        Returns:
            Composite rank score in [0.0, 1.0].
        """
        # ── Semantic similarity: claim headline vs article title ─────────
        article_title = article.title or ""
        try:
            if article_title:
                sem_sim = await self._embedder.compute_similarity(
                    claim_headline, article_title
                )
            else:
                # No title: compare claim headline vs first 200 chars of body
                body_prefix = (article.body or "")[:200]
                sem_sim = await self._embedder.compute_similarity(
                    claim_headline, body_prefix
                ) * 0.7  # Penalty for no title
        except Exception as exc:  # noqa: BLE001
            logger.debug("s07_sem_similarity_failed", error=str(exc))
            sem_sim = 0.0

        # ── Keyword overlap: claim keywords vs article title + body ──────
        article_text = f"{article.title or ''} {(article.body or '')[:500]}"
        article_keywords = extract_headline_keywords(article_text, top_n=8)
        kw_overlap = compute_keyword_overlap(claim_keywords, article_keywords)

        # ── Date bonus ────────────────────────────────────────────────────
        if claim_date is None or article.published_date is None:
            date_bonus = 0.5  # Unknown — neutral
        elif claim_date == article.published_date:
            date_bonus = 1.0
        else:
            # Partial credit within 7 days
            delta = abs((claim_date - article.published_date).days)
            date_bonus = max(0.0, 1.0 - (delta / 7.0))

        composite = (
            _W_SEM * sem_sim
            + _W_KW * kw_overlap
            + _W_DATE * date_bonus
        )
        return max(0.0, min(1.0, composite))

