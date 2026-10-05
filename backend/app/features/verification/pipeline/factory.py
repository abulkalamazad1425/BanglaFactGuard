"""
app/features/verification/pipeline/factory.py
================================================
The one place that assembles the verification pipeline's stage list.
`VerificationService` (POST /verify) and `PhotoCardService` both drive this
same pipeline, so a photo-card result is defensible on the same terms as a
typed claim.

    S01 normalise -> S02 reuse lookup -> S03 queries -> S04 search ->
    S05 fetch -> S06 extract -> S07 rank ->
    S08 source correspondence -> S09 headline alteration (title only) ->
    S10 body similarity (scores only) -> S11 date verification ->
    S12 result assembly -> S13 persistence / cache / delivery
"""

from __future__ import annotations

import httpx

from app.features.cache.cache_service import CacheService
from app.features.nlp.embedding_service import EmbeddingService
from app.features.nlp.ner_service import NERService
from app.features.nlp.nli_service import NLIService
from app.features.search.internal_site_client import InternalSiteSearchClient
from app.features.search.pygooglenews_client import PyGoogleNewsClient
from app.features.sources.repository import SourceRepository
from app.features.submissions.repository import (
    RetrievedArticleRepository,
    SubmissionRepository,
)
from app.features.verification.analysis.headline_comparison import HeadlineComparator
from app.features.verification.pipeline.context import PipelineStage
from app.features.verification.pipeline.stages.s01_normalizer import InputNormalizerStage
from app.features.verification.pipeline.stages.s02_cache_lookup import CacheLookupStage
from app.features.verification.pipeline.stages.s03_query_generator import QueryGeneratorStage
from app.features.verification.pipeline.stages.s04_source_search import SourceSearchStage
from app.features.verification.pipeline.stages.s05_evidence_retrieval import EvidenceRetrievalStage
from app.features.verification.pipeline.stages.s06_article_extractor import ArticleExtractorStage
from app.features.verification.pipeline.stages.s07_evidence_ranker import EvidenceRankerStage
from app.features.verification.pipeline.stages.s08_source_correspondence import SourceCorrespondenceStage
from app.features.verification.pipeline.stages.s09_headline_alteration import HeadlineAlterationStage
from app.features.verification.pipeline.stages.s10_body_similarity import BodySimilarityStage
from app.features.verification.pipeline.stages.s11_date_verification import DateVerificationStage
from app.features.verification.pipeline.stages.s12_result_assembly import ResultAssemblyStage
from app.features.verification.pipeline.stages.s13_result_persistence import ResultPersistenceStage
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
            pygooglenews_client=PyGoogleNewsClient(),
            internal_site_client=InternalSiteSearchClient(http_client),
            cache_service=cache_service,
        ),
        EvidenceRetrievalStage(http_client=http_client),
        ArticleExtractorStage(cache_service=cache_service),
        EvidenceRankerStage(embedding_service=embedding_service),
        SourceCorrespondenceStage(embedding_service=embedding_service),
        HeadlineAlterationStage(
            HeadlineComparator(nli_service, embedding_service, ner_service),
        ),
        BodySimilarityStage(embedding_service=embedding_service),
        DateVerificationStage(),
        ResultAssemblyStage(),
        ResultPersistenceStage(
            submission_repo=submission_repo,
            result_repo=result_repo,
            article_repo=article_repo,
            cache_service=cache_service,
            session=submission_repo.session,
        ),
    ]
