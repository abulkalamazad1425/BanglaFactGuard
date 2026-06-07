"""
app/services/verification_service.py
=======================================
VerificationService — top-level application service that wires the full
12-stage pipeline and exposes the public API for the FastAPI router.

## Responsibilities

1. Accept a `VerificationRequest` from the API layer.
2. Construct a `PipelineContext` from the request.
3. Build a `PipelineOrchestrator` with all 12 stage instances (all dependencies
   injected via constructor, provided by FastAPI DI).
4. Run the orchestrator.
5. Translate the completed `PipelineContext` into a `VerificationResponse`.
6. Handle cache-hit short-circuit (return cached response without pipeline run).

## DI pattern

`VerificationService` is instantiated per-request by FastAPI's DI system.
Each request gets its own service instance with a fresh `AsyncSession`.
ML services (EmbeddingService, NERService, NLIService) are application-scope
singletons injected once at startup.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

import structlog

from app.clients.brave_client import BraveSearchClient
from app.clients.ddg_client import DDGClient
from app.clients.google_rss_client import GoogleRSSClient
from app.core.exceptions import PipelineError
from app.pipelines.context import PipelineContext, build_context
from app.pipelines.orchestrator import PipelineOrchestrator
from app.pipelines.stages.s01_normalizer import InputNormalizerStage
from app.pipelines.stages.s02_cache_lookup import CacheLookupStage
from app.pipelines.stages.s03_query_generator import QueryGeneratorStage
from app.pipelines.stages.s04_source_search import SourceSearchStage
from app.pipelines.stages.s05_evidence_retrieval import EvidenceRetrievalStage
from app.pipelines.stages.s06_article_extractor import ArticleExtractorStage
from app.pipelines.stages.s07_evidence_ranker import EvidenceRankerStage
from app.pipelines.stages.s08_similarity_analyzer import SimilarityAnalyzerStage
from app.pipelines.stages.s09_contradiction_detector import ContradictionDetectorStage
from app.pipelines.stages.s10_manipulation_detector import ManipulationDetectorStage
from app.pipelines.stages.s11_classifier import ClassifierStage
from app.pipelines.stages.s12_persistence import PersistenceStage
from app.repositories.article_repository import ArticleRepository
from app.repositories.claim_repository import ClaimRepository
from app.repositories.result_repository import ResultRepository
from app.repositories.source_repository import SourceRepository
from app.schemas.verification import VerificationRequest, VerificationResponse
from app.services.cache_service import CacheService
from app.services.embedding_service import EmbeddingService
from app.services.ner_service import NERService
from app.services.nli_service import NLIService
import httpx

logger = structlog.get_logger(__name__)


class VerificationService:
    """
    Orchestrates the full 12-stage verification pipeline for a single claim.

    All dependencies are injected via __init__ and provided by FastAPI's DI.

    Args:
        claim_repo:         ClaimRepository (per-request).
        result_repo:        ResultRepository (per-request).
        article_repo:       ArticleRepository (per-request).
        source_repo:        SourceRepository (per-request).
        cache_service:      CacheService (singleton via app state).
        embedding_service:  EmbeddingService (singleton — model loaded at startup).
        ner_service:        NERService (singleton).
        nli_service:        NLIService (singleton).
        http_client:        Shared httpx.AsyncClient (singleton).
    """

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

    async def verify(self, request: VerificationRequest) -> VerificationResponse:
        """
        Run the full verification pipeline for a claim.

        Args:
            request: The validated VerificationRequest from the API.

        Returns:
            VerificationResponse with verdict, confidence, reasoning, and scores.

        Raises:
            PipelineError: On CRITICAL stage failure (S01, S11, S12).
        """
        log = logger.bind(claimed_source=request.claimed_source)

        # Build pipeline context
        context = build_context(
            headline=request.headline,
            claimed_source=request.claimed_source,
            news_body=request.news_body,
            published_date=request.published_date,
            force_refresh=request.force_refresh,
        )

        log.info(
            "verification_started",
            request_id=str(context.request_id),
            headline_preview=request.headline[:80],
        )

        # Build stage instances
        stages = self._build_stages()

        # Build orchestrator
        orchestrator = PipelineOrchestrator(
            stages=stages,
            claim_repo=self.claim_repo,
        )

        # Run pipeline
        context = await orchestrator.run(context)

        # Build and return response
        return self._build_response(context)

    async def get_result(self, claim_id: uuid.UUID) -> VerificationResponse | None:
        """
        Retrieve a previously computed verification result by claim ID.

        Args:
            claim_id: UUID of the verified_claims record.

        Returns:
            VerificationResponse or None if the claim does not exist / not yet completed.
        """
        result = await self.result_repo.get_by_claim_id(claim_id)
        if result is None:
            return None

        claim = await self.claim_repo.get_by_id_or_none(claim_id)
        if claim is None:
            return None

        from app.core.constants import VerificationLabel
        from app.schemas.scores import ManipulationFlagsSchema, VerificationScoresSchema

        return VerificationResponse(
            claim_id=claim_id,
            label=VerificationLabel(result.label),
            confidence=result.confidence,
            reasoning=result.reasoning or "",
            matched_articles=[],
            scores=VerificationScoresSchema(
                semantic_similarity=result.semantic_similarity,
                entity_match=result.entity_match,
                contradiction_score=result.contradiction_score,
                keyword_overlap=result.keyword_overlap,
                numerical_consistency=result.numerical_consistency,
            ),
            manipulation_flags=ManipulationFlagsSchema(),
            normalized_source=claim.normalized_source,
            cached=True,
            processing_time_ms=None,
            created_at=result.created_at,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_stages(self) -> list:
        """Construct all 12 stage instances with injected dependencies."""
        brave = BraveSearchClient(self.http_client)
        google_rss = GoogleRSSClient(self.http_client)
        ddg = DDGClient(self.http_client)

        return [
            InputNormalizerStage(source_repo=self.source_repo),
            CacheLookupStage(
                cache_service=self.cache_service,
                claim_repo=self.claim_repo,
                result_repo=self.result_repo,
            ),
            QueryGeneratorStage(),
            SourceSearchStage(
                brave_client=brave,
                google_rss_client=google_rss,
                ddg_client=ddg,
                cache_service=self.cache_service,
                http_client=self.http_client,
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
            ),
        ]

    def _build_response(self, context: PipelineContext) -> VerificationResponse:
        """Translate a completed PipelineContext into a VerificationResponse."""
        from app.core.constants import VerificationLabel
        from app.schemas.verification import VerificationScoresResponse

        # Cache hit — use cached fields
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

        # Full pipeline result
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
