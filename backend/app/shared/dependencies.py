"""
app/shared/dependencies.py
============================
FastAPI dependency injection providers.

Migrated from: app/api/dependencies.py

All request-scoped dependencies are factories that FastAPI resolves per request.
Application-scope singletons (ML models, HTTP client, Redis) are stored on
`app.state` during the lifespan startup and accessed here.

Dependency graph:
    get_async_session  → AsyncSession (per-request, auto-commit/rollback)
         │
         ├── get_claim_repo     → ClaimRepository
         ├── get_result_repo    → ResultRepository
         ├── get_article_repo   → ArticleRepository
         └── get_source_repo    → SourceRepository

    get_cache_service     → CacheService (app-scope singleton from app.state)
    get_embedding_service → EmbeddingService (singleton)
    get_ner_service       → NERService (singleton)
    get_nli_service       → NLIService (singleton)
    get_http_client       → httpx.AsyncClient (singleton)

    get_verification_service → VerificationService (per-request, all deps injected)
    get_source_service       → SourceService (per-request)
"""

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


# ---------------------------------------------------------------------------
# Database Session
# ---------------------------------------------------------------------------


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a per-request SQLAlchemy AsyncSession."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ---------------------------------------------------------------------------
# Repository dependencies (per-request)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# App-state singleton dependencies
# ---------------------------------------------------------------------------


def get_cache_service(request: Request) -> CacheService:
    """Return the CacheService singleton from app.state."""
    return request.app.state.cache_service


def get_embedding_service(request: Request) -> EmbeddingService:
    """Return the EmbeddingService singleton (LaBSE loaded at startup)."""
    return request.app.state.embedding_service


def get_ner_service(request: Request) -> NERService:
    """Return the NERService singleton (BanglaBERT loaded at startup)."""
    return request.app.state.ner_service


def get_nli_service(request: Request) -> NLIService:
    """Return the NLIService singleton (DeBERTa loaded at startup)."""
    return request.app.state.nli_service


def get_http_client(request: Request) -> httpx.AsyncClient:
    """Return the shared httpx.AsyncClient from app.state."""
    return request.app.state.http_client


# ---------------------------------------------------------------------------
# Service dependencies (per-request, all deps injected)
# ---------------------------------------------------------------------------


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
    """Construct a per-request VerificationService with all dependencies."""
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
    """Construct a per-request SourceService."""
    return SourceService(source_repo=source_repo)
