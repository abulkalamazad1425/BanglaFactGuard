from __future__ import annotations

import httpx
from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.cache.cache_service import CacheService
from app.features.nlp.embedding_service import EmbeddingService
from app.features.nlp.ner_service import NERService
from app.features.nlp.nli_service import NLIService
from app.features.photocard.service import PhotoCardService
from app.features.photocard.storage_service import PhotoCardStorageService
from app.features.sources.repository import SourceRepository
from app.features.submissions.repository import (
    PhotocardExtractionRepository,
    RetrievedArticleRepository,
    SubmissionRepository,
)
from app.features.verification.repository import ResultRepository
from app.shared.dependencies import (
    get_article_repo,
    get_async_session,
    get_cache_service,
    get_embedding_service,
    get_http_client,
    get_ner_service,
    get_nli_service,
    get_result_repo,
    get_source_repo,
    get_submission_repo,
)


def get_photocard_storage(request: Request) -> PhotoCardStorageService:
    storage = getattr(request.app.state, "photocard_storage", None)
    if storage is None:
        storage = PhotoCardStorageService()
        request.app.state.photocard_storage = storage
    return storage


async def get_extraction_repo(
    session: AsyncSession = Depends(get_async_session),
) -> PhotocardExtractionRepository:
    return PhotocardExtractionRepository(session)


async def get_photocard_service(
    storage: PhotoCardStorageService = Depends(get_photocard_storage),
    submission_repo: SubmissionRepository = Depends(get_submission_repo),
    extraction_repo: PhotocardExtractionRepository = Depends(get_extraction_repo),
    result_repo: ResultRepository = Depends(get_result_repo),
    article_repo: RetrievedArticleRepository = Depends(get_article_repo),
    source_repo: SourceRepository = Depends(get_source_repo),
    cache_service: CacheService = Depends(get_cache_service),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
    ner_service: NERService = Depends(get_ner_service),
    nli_service: NLIService = Depends(get_nli_service),
    http_client: httpx.AsyncClient = Depends(get_http_client),
) -> PhotoCardService:
    return PhotoCardService(
        storage=storage,
        submission_repo=submission_repo,
        extraction_repo=extraction_repo,
        result_repo=result_repo,
        article_repo=article_repo,
        source_repo=source_repo,
        cache_service=cache_service,
        embedding_service=embedding_service,
        ner_service=ner_service,
        nli_service=nli_service,
        http_client=http_client,
    )
