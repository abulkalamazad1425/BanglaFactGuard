"""
app/features/verification/pipeline/factory.py
================================================
The one place that assembles the verification pipeline's stage list.
`VerificationService` (POST /verify) and `PhotoCardService` (photo-card
step 2) both drive this exact same pipeline — a photo-card verdict has to be
defensible on the same terms as a typed claim — so both call this factory
instead of maintaining their own copy of the stage list.

Content is compared inside S11 (only once the source is confirmed) by the
local `ContentComparator`; it replaced the former S10 manipulation detector.
"""

from __future__ import annotations

import httpx

from app.features.cache.cache_service import CacheService
from app.features.nlp.embedding_service import EmbeddingService
from app.features.nlp.ner_service import NERService
from app.features.nlp.nli_service import NLIService
from app.features.search.duckduckgo_client import DuckDuckGoClient
from app.features.search.google_cse_client import GoogleCSEClient
from app.features.search.internal_site_client import InternalSiteSearchClient
from app.features.search.newsdata_client import NewsDataClient
from app.features.search.pygooglenews_client import PyGoogleNewsClient
from app.features.sources.repository import SourceRepository
from app.features.submissions.repository import (
    RetrievedArticleRepository,
    SubmissionRepository,
)
from app.features.verification.analysis.content_check import ContentComparator
from app.features.verification.pipeline.context import PipelineStage
from app.features.verification.pipeline.stages.s01_normalizer import (
    InputNormalizerStage,
)
from app.features.verification.pipeline.stages.s02_cache_lookup import CacheLookupStage
from app.features.verification.pipeline.stages.s03_query_generator import (
    QueryGeneratorStage,
)
from app.features.verification.pipeline.stages.s04_source_search import (
    SourceSearchStage,
)
from app.features.verification.pipeline.stages.s05_evidence_retrieval import (
    EvidenceRetrievalStage,
)
from app.features.verification.pipeline.stages.s06_article_extractor import (
    ArticleExtractorStage,
)
from app.features.verification.pipeline.stages.s07_evidence_ranker import (
    EvidenceRankerStage,
)
from app.features.verification.pipeline.stages.s08_similarity_analyzer import (
    SimilarityAnalyzerStage,
)
from app.features.verification.pipeline.stages.s09_contradiction_detector import (
    ContradictionDetectorStage,
)
from app.features.verification.pipeline.stages.s11_classifier import ClassifierStage
from app.features.verification.pipeline.stages.s12_persistence import PersistenceStage
from app.features.verification.repository import ResultRepository


def build_verification_stages(
    *,
    submission_repo: SubmissionRepository,
    result_repo: ResultRepository,
    article_repo: RetrievedArticleRepository,
    source_repo: SourceRepository,
    cache_service: CacheService,
    embedding_service: EmbeddingService,
    ner_service: NERService,
    nli_service: NLIService,
    http_client: httpx.AsyncClient,
) -> list[PipelineStage]:
    return [
        InputNormalizerStage(source_repo=source_repo),
        CacheLookupStage(
            cache_service=cache_service,
            submission_repo=submission_repo,
            result_repo=result_repo,
        ),
        QueryGeneratorStage(),
        SourceSearchStage(
            newsdata_client=NewsDataClient(http_client),
            google_cse_client=GoogleCSEClient(http_client),
            pygooglenews_client=PyGoogleNewsClient(),
            duckduckgo_client=DuckDuckGoClient(),
            internal_site_client=InternalSiteSearchClient(http_client),
            cache_service=cache_service,
        ),
        EvidenceRetrievalStage(http_client=http_client),
        ArticleExtractorStage(cache_service=cache_service),
        EvidenceRankerStage(embedding_service=embedding_service),
        SimilarityAnalyzerStage(
            embedding_service=embedding_service,
            ner_service=ner_service,
        ),
        ContradictionDetectorStage(nli_service=nli_service),
        ClassifierStage(
            content_comparator=ContentComparator(embedding_service, nli_service, ner_service),
        ),
        PersistenceStage(
            submission_repo=submission_repo,
            result_repo=result_repo,
            article_repo=article_repo,
            cache_service=cache_service,
            session=submission_repo.session,
        ),
    ]
