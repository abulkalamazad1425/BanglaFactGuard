"""
app/main.py
============
FastAPI application factory with async lifespan management.

Startup sequence (order matters):
  1. Initialise structlog JSON logging.
  2. Create async Redis client → CacheService.
  3. Create shared httpx.AsyncClient.
  4. Load LaBSE (EmbeddingService) — ~3-5 s, ~1.5 GB RAM.
  5. Load BanglaBERT NER (NERService) — ~2-3 s, ~800 MB RAM.
  6. Load DeBERTa NLI (NLIService) — ~2 s, ~500 MB RAM.
  7. Run Alembic auto-migrations (optional, controlled by env flag).
  8. Register all routers and middleware.

Shutdown sequence:
  1. Close httpx.AsyncClient (flush connections).
  2. Close Redis client.
  3. Log shutdown complete.

Total cold-start time: ~10-15 s on CPU. Pre-loaded models are shared
across all concurrent requests via app.state singleton references.
"""

from __future__ import annotations

import contextlib
import logging
from collections.abc import AsyncGenerator

import httpx
import redis.asyncio as aioredis
import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.middleware import CorrelationIDMiddleware, ProcessTimeMiddleware
from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.exceptions import BanglaFactGuardError
from app.core.logging import setup_logging
from app.features.cache.cache_service import CacheService
from app.features.nlp.embedding_service import EmbeddingService
from app.features.nlp.ner_service import NERService
from app.features.nlp.nli_service import NLIService

_SETTINGS = get_settings()
logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan: startup → serve → shutdown.

    All singletons are stored on `app.state` so FastAPI DI can access them
    without module-level globals.
    """
    setup_logging()
    log = structlog.get_logger("lifespan")
    log.info("bangla_fact_guard_starting", env=_SETTINGS.environment)

    # ── Redis ────────────────────────────────────────────────────────────
    redis_client = aioredis.from_url(
        _SETTINGS.redis.url,
        encoding="utf-8",
        decode_responses=False,
        max_connections=_SETTINGS.redis.max_connections,
    )
    app.state.cache_service = CacheService(redis_client)
    log.info("redis_connected", url=_SETTINGS.redis.url)

    # ── Shared HTTP client ───────────────────────────────────────────────
    app.state.http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(30.0),
        limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
        follow_redirects=True,
    )
    log.info("http_client_created")

    # ── ML Models ────────────────────────────────────────────────────────
    embedding_service = EmbeddingService(cache_service=app.state.cache_service)
    ner_service = NERService()
    nli_service = NLIService()

    if _SETTINGS.ml.load_models_on_startup:
        log.info("loading_ml_models")
        await embedding_service.load()     # LaBSE ~3-5 s
        await ner_service.load()           # BanglaBERT NER ~2-3 s
        await nli_service.load()           # DeBERTa NLI ~2 s
        log.info("ml_models_loaded")
    else:
        log.warning("ml_models_skipped_load_on_startup_disabled")

    app.state.embedding_service = embedding_service
    app.state.ner_service = ner_service
    app.state.nli_service = nli_service

    log.info("bangla_fact_guard_ready")

    yield  # ─── Application is serving requests ───────────────────────

    # ── Shutdown ─────────────────────────────────────────────────────────
    log.info("bangla_fact_guard_shutting_down")
    await app.state.http_client.aclose()
    await redis_client.aclose()
    log.info("bangla_fact_guard_shutdown_complete")


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------


def create_app() -> FastAPI:
    """
    Construct and configure the FastAPI application.

    Returns:
        Configured FastAPI instance ready for ASGI serving.
    """
    app = FastAPI(
        title="BanglaFactGuard",
        summary="Multimodal Bangla Source-Based Fact Verification API",
        description=(
            "Given a news article and a claimed source, BanglaFactGuard determines "
            "whether that source actually published the article using a 12-stage "
            "verification pipeline combining search, NLU, NER, and NLI."
        ),
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # ── CORS ─────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_SETTINGS.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    # ── Custom middleware (order: outermost → innermost) ─────────────────
    app.add_middleware(ProcessTimeMiddleware)
    app.add_middleware(CorrelationIDMiddleware)

    # ── Routers ──────────────────────────────────────────────────────────
    app.include_router(api_router)

    # ── Exception handlers ───────────────────────────────────────────────
    _register_exception_handlers(app)

    return app


def _register_exception_handlers(app: FastAPI) -> None:
    """Register global exception handlers for domain and unexpected errors."""

    @app.exception_handler(BanglaFactGuardError)
    async def domain_error_handler(
        request: Request, exc: BanglaFactGuardError
    ) -> JSONResponse:
        logger.warning(
            "domain_error",
            path=str(request.url),
            error_type=type(exc).__name__,
            message=exc.message,
        )
        return JSONResponse(
            status_code=exc.http_status_code,
            content={
                "error": type(exc).__name__,
                "message": exc.message,
                "details": exc.details,
                "request_id": getattr(request.state, "request_id", None),
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        logger.error(
            "unhandled_exception",
            path=str(request.url),
            error=str(exc),
            exc_info=True,
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": "InternalServerError",
                "message": "An unexpected error occurred.",
                "request_id": getattr(request.state, "request_id", None),
            },
        )


# ---------------------------------------------------------------------------
# ASGI entry-point
# ---------------------------------------------------------------------------

app = create_app()
