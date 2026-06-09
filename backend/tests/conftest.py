"""
tests/conftest.py
==================
Shared pytest fixtures for unit and integration tests.

Features:
1. SQLite in-memory async database setup (`sqlite+aiosqlite://`).
2. Automatic repository overrides for the FastAPI dependency injection.
3. Globally mocked Machine Learning services (Embedding, NER, NLI) to avoid downloading weights or running heavy models.
4. Globally mocked search clients (Brave, Google RSS, DuckDuckGo).
5. Clean HTTPX AsyncClient for FastAPI endpoint testing.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from datetime import datetime
import json
import os
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import numpy as np
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Force test configuration
os.environ["ENVIRONMENT"] = "development"
os.environ["DB_HOST"] = "localhost"
os.environ["DB_PORT"] = "5432"
os.environ["DB_NAME"] = "test"
os.environ["DB_USER"] = "postgres"
os.environ["DB_PASSWORD"] = "postgres"
os.environ["REDIS_HOST"] = "localhost"
os.environ["REDIS_PORT"] = "6379"

from app.shared.dependencies import get_async_session
from app.core.config import get_settings
from app.shared.models_registry import Base
from app.main import create_app
from app.features.sources.models import SourceRegistry
from app.features.verification.schemas import NLIScoresSchema
from app.features.cache.cache_service import CacheService
from app.features.nlp.embedding_service import EmbeddingService
from app.features.nlp.ner_service import NERService
from app.features.nlp.nli_service import NLIService

# In-memory SQLite for test isolation
SQLITE_URL = "sqlite+aiosqlite:///:memory:"

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for each test case."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
    yield loop
    loop.close()

# ---------------------------------------------------------------------------
# Database Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
async def test_engine():
    """Create async SQLite engine for tests."""
    engine = create_async_engine(SQLITE_URL, echo=False)
    async with engine.begin() as conn:
        # Create all tables on SQLite
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()

@pytest.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Provide a transactional in-memory database session."""
    session_local = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )
    async with session_local() as session:
        yield session
        # Always rollback to keep tests isolated
        await session.rollback()

# ---------------------------------------------------------------------------
# Cache Mock Fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_redis() -> MagicMock:
    """Mock Redis client for CacheService."""
    client = MagicMock()
    # Mock basic string operations
    client.get = AsyncMock(return_value=None)
    client.set = AsyncMock(return_value=True)
    client.delete = AsyncMock(return_value=True)
    return client

@pytest.fixture
def test_cache_service(mock_redis) -> CacheService:
    """CacheService instance initialized with mocked Redis client."""
    return CacheService(mock_redis)

# ---------------------------------------------------------------------------
# ML Services Mock Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_embedding_service() -> MagicMock:
    """Mock EmbeddingService to avoid loading LaBSE."""
    service = MagicMock(spec=EmbeddingService)
    service.load = AsyncMock()
    # Mock 768-dim L2-normalized vector
    mock_vector = np.zeros(768, dtype=np.float32)
    mock_vector[0] = 1.0  # Normalized
    service.encode = AsyncMock(return_value=mock_vector)
    service.encode_batch = AsyncMock(return_value=[mock_vector])
    service.compute_similarity = AsyncMock(return_value=0.90)
    return service

@pytest.fixture
def mock_ner_service() -> MagicMock:
    """Mock NERService to avoid loading BanglaBERT NER."""
    service = MagicMock(spec=NERService)
    service.load = AsyncMock()
    service.extract_entities = AsyncMock(return_value=["ঢাকা", "বাংলাদেশ"])
    service.compute_entity_overlap = MagicMock(return_value=1.0)
    return service

@pytest.fixture
def mock_nli_service() -> MagicMock:
    """Mock NLIService to avoid loading DeBERTa NLI."""
    service = MagicMock(spec=NLIService)
    service.load = AsyncMock()
    service.predict = AsyncMock(
        return_value=NLIScoresSchema(entailment=0.90, contradiction=0.05, neutral=0.05)
    )
    return service

# ---------------------------------------------------------------------------
# Search Client Mock Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_search_clients() -> dict[str, MagicMock]:
    """Mock all search providers to return a predefined domain search result."""
    from app.features.search.newsdata_client import NewsDataClient
    from app.features.search.google_cse_client import GoogleCSEClient
    from app.features.search.pygooglenews_client import PyGoogleNewsClient
    from app.features.search.duckduckgo_client import DuckDuckGoClient

    newsdata = MagicMock(spec=NewsDataClient)
    newsdata.search_entries = AsyncMock(return_value=[("https://prothomalo.com/article/123", "শেখ হাসিনা নতুন উড়ালসড়ক উদ্বোধন করলেন")])

    google_cse = MagicMock(spec=GoogleCSEClient)
    google_cse.search_entries = AsyncMock(return_value=[])

    pygooglenews = MagicMock(spec=PyGoogleNewsClient)
    pygooglenews.search_entries = AsyncMock(return_value=[])

    ddg = MagicMock(spec=DuckDuckGoClient)
    ddg.search_entries = AsyncMock(return_value=[])

    return {
        "newsdata": newsdata,
        "google_cse": google_cse,
        "pygooglenews": pygooglenews,
        "ddg": ddg,
    }

# ---------------------------------------------------------------------------
# Application & FastAPI Client Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
async def app(
    db_session,
    test_cache_service,
    mock_embedding_service,
    mock_ner_service,
    mock_nli_service,
    mock_search_clients,
) -> FastAPI:
    """
    Construct FastAPI app with overridden dependency injection.
    """
    # Overwrite startup lifespans by patching ML loads
    with (
        patch("app.main.lifespan") as mock_lifespan,
        patch("app.features.nlp.embedding_service.EmbeddingService.load", new_callable=AsyncMock),
        patch("app.features.nlp.ner_service.NERService.load", new_callable=AsyncMock),
        patch("app.features.nlp.nli_service.NLIService.load", new_callable=AsyncMock),
    ):
        application = create_app()
        
        # Inject mocked services into app.state
        application.state.cache_service = test_cache_service
        application.state.embedding_service = mock_embedding_service
        application.state.ner_service = mock_ner_service
        application.state.nli_service = mock_nli_service
        application.state.http_client = MagicMock()
        
        # Override dependency resolution
        application.dependency_overrides[get_async_session] = lambda: db_session

        yield application

        application.dependency_overrides.clear()

@pytest.fixture
async def client(app) -> AsyncGenerator[httpx.AsyncClient, None]:
    """Test client using HTTPX."""
    import httpx
    async with httpx.AsyncClient(app=app, base_url="http://testserver") as async_client:
        yield async_client

