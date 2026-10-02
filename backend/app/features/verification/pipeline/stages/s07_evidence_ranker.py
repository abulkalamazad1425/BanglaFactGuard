from __future__ import annotations

import structlog

from urllib.parse import urlparse
from Levenshtein import ratio

from app.core.config import get_settings
from app.core.constants import PipelineStageID
from app.features.verification.pipeline.context import PipelineContext
from app.features.verification.pipeline.stages.cross_encoder_reranker import (
    CrossEncoderReranker,
)
from app.features.articles.schemas import RankedArticleSchema
from app.features.nlp.embedding_service import EmbeddingService
from app.shared.utils.keyword_extractor import (
    compute_keyword_overlap,
    extract_headline_keywords,
)
from app.shared.utils.bangla_normalizer import normalize_bangla_text

logger = structlog.get_logger(__name__)
_SETTINGS = get_settings()

# Retrieval relevance only: how likely is this article the report the claim is
# about. The claimed date is deliberately NOT a ranking input - a wrong claimed
# date must not push the genuine report below a same-day unrelated one (the
# date is compared separately, in S11, against the report's datePublished).
_W_SEM = 0.55
_W_KW = 0.25
_W_DOMAIN = 0.20


class EvidenceRankerStage:

    stage_id = PipelineStageID.S07_EVIDENCE_RANKER

    def __init__(self, embedding_service: EmbeddingService) -> None:
        self._embedder = embedding_service
        self._max_ranked = _SETTINGS.ml.max_ranked_articles
        self._min_score = _SETTINGS.ml.min_rank_score
        self._reranker = CrossEncoderReranker()

    async def execute(self, context: PipelineContext) -> PipelineContext:
        articles = context.extracted_articles

        if not articles:
            logger.debug("s07_no_articles_to_rank")
            context.ranked_articles = []
            context.top_article = None
            return context

        claim_headline = context.normalized_headline
        claim_keywords = context.claim_keywords or extract_headline_keywords(
            claim_headline
        )

        scored: list[tuple[float, RankedArticleSchema]] = []

        for article in articles:
            score = await self._score_article(
                article=article,
                claim_headline=claim_headline,
                claim_keywords=claim_keywords,
                claim_date=context.published_date,
                context=context,
            )
            scored.append((score, article))

        scored.sort(key=lambda x: x[0], reverse=True)

        ranked: list[RankedArticleSchema] = []
        for score, article in scored:
            if score < self._min_score:
                break

            updated = article.model_copy(update={"rank_score": round(score, 4)})
            ranked.append(updated)
            if len(ranked) >= self._max_ranked:
                break

        if not ranked and scored:
            best_score, best_article = scored[0]
            ranked = [
                RankedArticleSchema(
                    **{**best_article.model_dump(), "rank_score": round(best_score, 4)}
                )
            ]

        if len(ranked) > 3:
            logger.info("s07_reranking_articles", count=len(ranked))
            ranked = await self._reranker.rerank(
                claim_headline, ranked, top_k=self._max_ranked
            )

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
        context: PipelineContext,
    ) -> float:

        article_title = article.title or ""
        try:
            if article_title:
                sem_sim = await self._embedder.compute_similarity(
                    claim_headline, article_title
                )
            else:

                body_prefix = (article.body or "")[:400]
                if body_prefix:
                    sem_sim = await self._embedder.compute_similarity(
                        claim_headline, body_prefix
                    )
                else:
                    sem_sim = 0.0
        except Exception as exc:
            logger.debug("s07_sem_similarity_failed", error=str(exc))
            sem_sim = 0.0

        article_text = f"{article.title or ''} {(article.body or '')[:500]}"
        article_keywords = extract_headline_keywords(article_text, top_n=8)
        kw_overlap = compute_keyword_overlap(claim_keywords, article_keywords)

        domain_bonus = self._source_domain_bonus(context, article)

        composite = (
            _W_SEM * sem_sim
            + _W_KW * kw_overlap
            + _W_DOMAIN * domain_bonus
        )

        if article_title:
            sim = ratio(
                normalize_bangla_text(claim_headline),
                normalize_bangla_text(article_title),
            )
            if sim > 0.85:
                composite += 0.15
            elif sim > 0.70:
                composite += 0.08

        return max(0.0, min(1.0, composite))

    def _source_domain_bonus(
        self, context: PipelineContext, article: RankedArticleSchema
    ) -> float:
        if not context.normalized_source:
            return 0.0

        def extract_domain(url: str) -> str:
            if not url:
                return ""

            if not url.startswith(("http://", "https://")):
                url = "https://" + url
            parsed = urlparse(url)
            return parsed.netloc.replace("www.", "")

        claim_domain = extract_domain(context.normalized_source)
        article_domain = extract_domain(article.url)
        if claim_domain == article_domain:
            return 1.0
        return 0.0
