
from __future__ import annotations

import uuid
from datetime import date, datetime

import structlog

from app.features.search.newsdata_client import NewsDataClient
from app.features.search.google_cse_client import GoogleCSEClient
from app.features.search.pygooglenews_client import PyGoogleNewsClient
from app.features.search.duckduckgo_client import DuckDuckGoClient
from app.features.search.internal_site_client import InternalSiteSearchClient
from app.core.exceptions import PipelineError
from app.features.verification.pipeline.context import PipelineContext, build_context
from app.features.verification.pipeline.orchestrator import PipelineOrchestrator
from app.features.verification.pipeline.stages.s01_normalizer import InputNormalizerStage
from app.features.verification.pipeline.stages.s02_cache_lookup import CacheLookupStage
from app.features.verification.pipeline.stages.s03_query_generator import QueryGeneratorStage
from app.features.verification.pipeline.stages.s04_source_search import SourceSearchStage
from app.features.verification.pipeline.stages.s05_evidence_retrieval import EvidenceRetrievalStage
from app.features.verification.pipeline.stages.s06_article_extractor import ArticleExtractorStage
from app.features.verification.pipeline.stages.s07_evidence_ranker import EvidenceRankerStage
from app.features.verification.pipeline.stages.s08_similarity_analyzer import SimilarityAnalyzerStage
from app.features.verification.pipeline.stages.s09_contradiction_detector import ContradictionDetectorStage
from app.features.verification.pipeline.stages.s10_manipulation_detector import ManipulationDetectorStage
from app.features.verification.pipeline.stages.s11_classifier import ClassifierStage
from app.features.verification.pipeline.stages.s12_persistence import PersistenceStage
from app.features.articles.repository import ArticleRepository
from app.features.verification.repository import ClaimRepository
from app.features.verification.repository import ResultRepository
from app.features.sources.repository import SourceRepository
from app.features.verification.schemas import VerificationRequest, VerificationResponse
from app.features.cache.cache_service import CacheService
from app.features.nlp.embedding_service import EmbeddingService
from app.features.nlp.ner_service import NERService
from app.features.nlp.nli_service import NLIService
import httpx

logger = structlog.get_logger(__name__)


class VerificationService:

    def __init__(
        self,
        claim_repo: ClaimRepository,
        result_repo: ResultRepository,
        article_repo: ArticleRepository,
        source_repo: SourceRepository,
        cache_service: CacheService,
        embedding_service: EmbeddingService,
        ner_service: NERService,
        nli_service: NLIService,
        http_client: httpx.AsyncClient,
    ) -> None:
        self.claim_repo = claim_repo
        self.result_repo = result_repo
        self.article_repo = article_repo
        self.source_repo = source_repo
        self.cache_service = cache_service
        self.embedding_service = embedding_service
        self.ner_service = ner_service
        self.nli_service = nli_service
        self.http_client = http_client

    async def verify(self, request: VerificationRequest, *, submitter_id: uuid.UUID | None = None) -> VerificationResponse:
        log = logger.bind(claimed_source=request.claimed_source)


        context = build_context(
            headline=request.headline,
            claimed_source=request.claimed_source,
            news_body=request.news_body,
            published_date=request.published_date,
            force_refresh=request.force_refresh,
            submitter_id=submitter_id,
        )

        log.info(
            "verification_started",
            request_id=str(context.request_id),
            headline_preview=request.headline[:80],
        )


        stages = self._build_stages()


        orchestrator = PipelineOrchestrator(
            stages=stages,
            claim_repo=self.claim_repo,
        )


        context = await orchestrator.run(context)


        return self._build_response(context)

    async def get_result(self, claim_id: uuid.UUID) -> VerificationResponse | None:
        result = await self.result_repo.get_by_claim_id(claim_id)
        if result is None:
            return None

        claim = await self.claim_repo.get_by_id_or_none(claim_id)
        if claim is None:
            return None

        from app.core.constants import VerificationLabel
        from app.features.verification.schemas import (
            ManipulationFlagsSchema,
            VerificationScoresResponse,
        )
        from app.features.articles.schemas import RankedArticleSchema
        from sqlalchemy import select
        from app.features.articles.models import RetrievedArticle




        art_stmt = (
            select(RetrievedArticle)
            .where(
                RetrievedArticle.claim_id == claim_id,
                RetrievedArticle.extraction_success.is_(True),
            )
            .order_by(RetrievedArticle.rank_score.desc())
            .limit(3)
        )
        art_rows = list((await self.result_repo.session.execute(art_stmt)).scalars().all())
        from app.core.constants import SearchProvider
        matched_articles = [
            RankedArticleSchema(
                url=a.url,
                title=a.title,
                author=a.author,
                published_date=a.published_date,
                body=a.body,
                rank_score=a.rank_score or 0.0,
                search_provider=SearchProvider.INTERNAL_SITE,
                extraction_method=a.extraction_method,
            )
            for a in art_rows
        ]




        cached_scores = None
        cached_flags = None
        try:
            import json
            if claim.claim_hash:
                raw = await self.cache_service.get_claim_result(claim.claim_hash)
                if raw:
                    cached_data = json.loads(raw)
                    s = cached_data.get("scores", {})
                    cached_scores = VerificationScoresResponse(
                        semantic_similarity=s.get("semantic_similarity"),
                        entity_match=s.get("entity_match"),
                        keyword_overlap=s.get("keyword_overlap"),
                        numerical_consistency=s.get("numerical_consistency"),
                        contradiction_score=s.get("contradiction_score"),
                        headline_similarity=s.get("headline_similarity"),
                        body_similarity=s.get("body_similarity"),
                    )
                    f = cached_data.get("manipulation_flags", {})
                    cached_flags = ManipulationFlagsSchema(
                        headline_manipulated=f.get("headline_manipulated", False),
                        body_altered=f.get("body_altered", False),
                        numbers_altered=f.get("numbers_altered", False),
                        entities_replaced=f.get("entities_replaced", False),
                    )
        except Exception:
            pass

        scores = cached_scores or VerificationScoresResponse(
            semantic_similarity=result.semantic_similarity,
            entity_match=result.entity_match,
            contradiction_score=result.contradiction_score,
            keyword_overlap=result.keyword_overlap,
            numerical_consistency=result.numerical_consistency,
        )
        flags = cached_flags or ManipulationFlagsSchema()

        return VerificationResponse(
            claim_id=claim_id,
            label=VerificationLabel(result.label),
            confidence=result.confidence,
            reasoning=result.reasoning or "",
            matched_articles=matched_articles,
            scores=scores,
            manipulation_flags=flags,
            normalized_source=claim.normalized_source,
            cached=True,
            processing_time_ms=None,
            created_at=result.created_at,
        )





    def _build_stages(self) -> list:
        newsdata = NewsDataClient(self.http_client)
        google_cse = GoogleCSEClient(self.http_client)
        pygooglenews = PyGoogleNewsClient()
        duckduckgo = DuckDuckGoClient()

        return [
            InputNormalizerStage(source_repo=self.source_repo),
            CacheLookupStage(
                cache_service=self.cache_service,
                claim_repo=self.claim_repo,
                result_repo=self.result_repo,
            ),
            QueryGeneratorStage(),
            SourceSearchStage(
                newsdata_client=newsdata,
                google_cse_client=google_cse,
                pygooglenews_client=pygooglenews,
                duckduckgo_client=duckduckgo,
                internal_site_client=InternalSiteSearchClient(self.http_client),
                cache_service=self.cache_service,
            ),
            EvidenceRetrievalStage(http_client=self.http_client),
            ArticleExtractorStage(cache_service=self.cache_service),
            EvidenceRankerStage(embedding_service=self.embedding_service),
            SimilarityAnalyzerStage(
                embedding_service=self.embedding_service,
                ner_service=self.ner_service,
            ),
            ContradictionDetectorStage(nli_service=self.nli_service),
            ManipulationDetectorStage(embedding_service=self.embedding_service),
            ClassifierStage(),
            PersistenceStage(
                claim_repo=self.claim_repo,
                result_repo=self.result_repo,
                article_repo=self.article_repo,
                cache_service=self.cache_service,
                session=self.claim_repo.session,
            ),
        ]

    def _build_response(self, context: PipelineContext) -> VerificationResponse:
        from app.core.constants import VerificationLabel
        from app.features.verification.schemas import VerificationScoresResponse


        if context.cache_hit:
            return VerificationResponse(
                claim_id=context.claim_id or uuid.uuid4(),
                label=context.cached_label or VerificationLabel.NOT_FOUND_IN_CLAIMED_SOURCE,
                confidence=context.cached_confidence or 0.0,
                reasoning=context.cached_reasoning or "",
                matched_articles=context.cached_matched_articles,
                scores=VerificationScoresResponse.model_validate(
                    (context.cached_scores or context.scores).model_dump()
                ),
                manipulation_flags=context.cached_manipulation_flags or context.manipulation_flags,
                normalized_source=context.normalized_source,
                cached=True,
                processing_time_ms=None,
                created_at=datetime.utcnow(),
            )


        return VerificationResponse(
            claim_id=context.claim_id or uuid.uuid4(),
            label=context.label or VerificationLabel.NOT_FOUND_IN_CLAIMED_SOURCE,
            confidence=context.confidence,
            reasoning=context.reasoning,
            matched_articles=context.ranked_articles[:3],
            scores=VerificationScoresResponse.model_validate(context.scores.model_dump()),
            manipulation_flags=context.manipulation_flags,
            normalized_source=context.normalized_source,
            cached=False,
            processing_time_ms=context.elapsed_ms,
            created_at=datetime.utcnow(),
        )



