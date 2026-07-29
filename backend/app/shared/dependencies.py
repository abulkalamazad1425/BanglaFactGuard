
from __future__ import annotations

from collections.abc import AsyncGenerator

import httpx
from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.engine import AsyncSessionLocal
from app.features.articles.repository import ArticleRepository
from app.features.cache.cache_service import CacheService
from app.features.nlp.embedding_service import EmbeddingService
from app.features.nlp.ner_service import NERService
from app.features.nlp.nli_service import NLIService
from app.features.sources.repository import SourceRepository
from app.features.sources.service import SourceService
from app.features.verification.repository import ClaimRepository, ResultRepository
from app.features.verification.service import VerificationService







async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise







async def get_claim_repo(
    session: AsyncSession = Depends(get_async_session),
) -> ClaimRepository:
    return ClaimRepository(session)


async def get_result_repo(
    session: AsyncSession = Depends(get_async_session),
) -> ResultRepository:
    return ResultRepository(session)


async def get_article_repo(
    session: AsyncSession = Depends(get_async_session),
) -> ArticleRepository:
    return ArticleRepository(session)


async def get_source_repo(
    session: AsyncSession = Depends(get_async_session),
) -> SourceRepository:
    return SourceRepository(session)







def get_cache_service(request: Request) -> CacheService:
    return request.app.state.cache_service


def get_embedding_service(request: Request) -> EmbeddingService:
    return request.app.state.embedding_service


def get_ner_service(request: Request) -> NERService:
    return request.app.state.ner_service


def get_nli_service(request: Request) -> NLIService:
    return request.app.state.nli_service


def get_http_client(request: Request) -> httpx.AsyncClient:
    return request.app.state.http_client







async def get_verification_service(
    claim_repo: ClaimRepository = Depends(get_claim_repo),
    result_repo: ResultRepository = Depends(get_result_repo),
    article_repo: ArticleRepository = Depends(get_article_repo),
    source_repo: SourceRepository = Depends(get_source_repo),
    cache_service: CacheService = Depends(get_cache_service),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
    ner_service: NERService = Depends(get_ner_service),
    nli_service: NLIService = Depends(get_nli_service),
    http_client: httpx.AsyncClient = Depends(get_http_client),
) -> VerificationService:
    return VerificationService(
        claim_repo=claim_repo,
        result_repo=result_repo,
        article_repo=article_repo,
        source_repo=source_repo,
        cache_service=cache_service,
        embedding_service=embedding_service,
        ner_service=ner_service,
        nli_service=nli_service,
        http_client=http_client,
    )


async def get_source_service(
    source_repo: SourceRepository = Depends(get_source_repo),
) -> SourceService:
    return SourceService(source_repo=source_repo)
