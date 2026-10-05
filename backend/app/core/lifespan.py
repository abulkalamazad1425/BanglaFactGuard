from __future__ import annotations

import contextlib
from collections.abc import AsyncGenerator

import httpx
import redis.asyncio as aioredis
import structlog
from fastapi import FastAPI

from app.core.config import get_settings
from app.core.logging import setup_logging
from app.features.cache.cache_service import CacheService
from app.features.multimodal.pipeline.model_loader import MultimodalModelLoader
from app.features.multimodal.storage_service import MultimodalStorageService
from app.features.nlp.embedding_service import EmbeddingService
from app.features.nlp.ner_service import NERService
from app.features.nlp.nli_service import NLIService
from app.features.photocard.ocr_service import BanglaOcrService
from app.features.photocard.storage_service import PhotoCardStorageService

_SETTINGS = get_settings()


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    setup_logging()
    log = structlog.get_logger("lifespan")
    log.info("bangla_fact_guard_starting", env=_SETTINGS.environment)

    redis_client = aioredis.from_url(
        _SETTINGS.redis.url,
        encoding="utf-8",
        decode_responses=False,
        max_connections=_SETTINGS.redis.max_connections,
    )
    app.state.cache_service = CacheService(redis_client)
    log.info("redis_connected", url=_SETTINGS.redis.url)

    app.state.http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(30.0),
        limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
        follow_redirects=True,
    )
    log.info("http_client_created")

    embedding_service = EmbeddingService(cache_service=app.state.cache_service)
    ner_service = NERService()
    nli_service = NLIService()

    if _SETTINGS.ml.load_models_on_startup:
        log.info("loading_ml_models")
        try:
            await embedding_service.load()
        except Exception as exc:
            log.error(
                "labse_load_failed",
                error=str(exc),
                hint="Increase Windows virtual memory (pagefile) or set ML_LOAD_MODELS_ON_STARTUP=false",
            )

        try:
            await ner_service.load()
        except Exception as exc:
            log.error("ner_load_failed", error=str(exc))
        try:
            await nli_service.load()
        except Exception as exc:
            log.error("nli_load_failed", error=str(exc))
        log.info("ml_models_load_complete")
    else:
        log.warning("ml_models_skipped_load_on_startup_disabled")

    app.state.embedding_service = embedding_service
    app.state.ner_service = ner_service
    app.state.nli_service = nli_service

    multimodal_loader = MultimodalModelLoader()
    if _SETTINGS.multimodal.load_on_startup:
        log.info("loading_multimodal_model", model_dir=_SETTINGS.multimodal.model_dir)
        try:
            await multimodal_loader.load()
            log.info("multimodal_model_loaded")
        except Exception as exc:
            log.error(
                "multimodal_model_load_failed",
                error=str(exc),
                hint="Set MULTIMODAL_LOAD_ON_STARTUP=false to start without model weights",
            )

    else:
        log.warning("multimodal_model_load_skipped")
    app.state.multimodal_loader = multimodal_loader

    multimodal_storage = MultimodalStorageService()
    try:
        await multimodal_storage.ensure_bucket()
    except Exception as exc:
        log.warning("minio_bucket_ensure_failed", error=str(exc))

    app.state.multimodal_storage = multimodal_storage

    photocard_ocr = BanglaOcrService()
    if _SETTINGS.ocr.load_on_startup:
        try:
            await photocard_ocr.load()
        except Exception as exc:
            log.error(
                "photocard_ocr_load_failed",
                error=str(exc),
                hint=(
                    "Install Tesseract with the 'ben' traineddata (and set "
                    "OCR_TESSERACT_CMD if it is not on PATH), or `pip install "
                    "easyocr`. Photo-card endpoints stay unavailable until one "
                    "engine loads; every other feature is unaffected."
                ),
            )
    else:
        # The engine loads on first use instead — EasyOCR downloads ~100 MB of
        # weights the first time, which should not block application startup.
        log.info("photocard_ocr_lazy_load")
    app.state.photocard_ocr = photocard_ocr

    photocard_storage = PhotoCardStorageService()
    try:
        await photocard_storage.ensure_bucket()
    except Exception as exc:
        log.warning("photocard_bucket_ensure_failed", error=str(exc))
    app.state.photocard_storage = photocard_storage

    # Durable job worker: drains verification_jobs (text + photo-card). Jobs
    # accepted before a restart, or left RUNNING by a crashed process, are
    # picked up here once their heartbeat is stale.
    app.state.job_worker = None
    if _SETTINGS.jobs.enabled:
        from app.features.verification.jobs import JobDeps, VerificationJobWorker

        worker = VerificationJobWorker(
            JobDeps.from_app_state(app.state),
            concurrency=_SETTINGS.jobs.max_concurrent,
            poll_interval_s=_SETTINGS.jobs.poll_interval_seconds,
            stale_after_s=_SETTINGS.jobs.stale_after_seconds,
            heartbeat_interval_s=_SETTINGS.jobs.heartbeat_interval_seconds,
        )
        worker.start()
        app.state.job_worker = worker
    else:
        log.warning("job_worker_disabled")

    from app.features.notifications.delivery import ResultDeliveryWorker
    app.state.result_delivery_worker = ResultDeliveryWorker()
    app.state.result_delivery_worker.start()

    log.info("bangla_fact_guard_ready")

    yield

    log.info("bangla_fact_guard_shutting_down")
    if app.state.job_worker is not None:
        await app.state.job_worker.stop()
    await app.state.result_delivery_worker.stop()
    await app.state.http_client.aclose()
    await redis_client.aclose()
    log.info("bangla_fact_guard_shutdown_complete")
