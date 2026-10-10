"""App lifespan with every external service (Redis, MinIO, models, workers)
faked; the startup/shutdown code itself is real."""

from __future__ import annotations

from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI

from app.core import lifespan as lifespan_module


class _Worker:
    def __init__(self, name, events):
        self.name, self.events = name, events

    def start(self):
        self.events.append(f"{self.name}.start")

    async def stop(self):
        self.events.append(f"{self.name}.stop")


def _patches(stack: ExitStack, events: list, *, models: bool, jobs: bool, broken: bool) -> None:
    settings = lifespan_module._SETTINGS
    failing = AsyncMock(side_effect=RuntimeError("unavailable"))
    storage = MagicMock(ensure_bucket=failing if broken else AsyncMock())
    for p in (
        patch.object(settings.ml, "load_models_on_startup", models),
        patch.object(settings.multimodal, "load_on_startup", models),
        patch.object(settings.jobs, "enabled", jobs),
        patch.object(lifespan_module.aioredis, "from_url", return_value=MagicMock(
            aclose=AsyncMock(side_effect=lambda: events.append("redis.close")))),
        patch.object(lifespan_module, "MultimodalStorageService", return_value=storage),
        patch.object(lifespan_module, "PhotoCardStorageService", return_value=storage),
        patch.object(lifespan_module.EmbeddingService, "load", failing),
        patch.object(lifespan_module.NERService, "load", failing),
        patch.object(lifespan_module.NLIService, "load", failing),
        patch.object(lifespan_module.MultimodalModelLoader, "load", failing),
        patch("app.features.verification.jobs.VerificationJobWorker", side_effect=lambda *a, **k: _Worker("jobs", events)),
        patch("app.features.verification.jobs.JobDeps.from_app_state", return_value=SimpleNamespace()),
        patch("app.features.notifications.delivery.ResultDeliveryWorker", side_effect=lambda: _Worker("delivery", events)),
        patch("app.features.expert_review.escalation.EscalationWorker", side_effect=lambda: _Worker("escalation", events)),
        patch.object(lifespan_module, "close_engine", AsyncMock(side_effect=lambda: events.append("engine.dispose"))),
    ):
        stack.enter_context(p)


async def test_restartable_and_stops_workers_before_clients_and_engine():
    events: list[str] = []
    with ExitStack() as stack:
        _patches(stack, events, models=False, jobs=True, broken=False)
        for _ in range(2):
            app = FastAPI()
            async with lifespan_module.lifespan(app):
                assert app.state.job_worker is not None
                assert app.state.multimodal_loader.is_loaded is False
            await app.state.http_client.aclose()  # idempotent; already closed

    cycle = [
        "jobs.start", "delivery.start", "escalation.start",
        "jobs.stop", "delivery.stop", "escalation.stop", "redis.close", "engine.dispose",
    ]
    assert events == cycle + cycle


async def test_unavailable_models_and_storage_never_prevent_startup():
    events: list[str] = []
    with ExitStack() as stack:
        _patches(stack, events, models=True, jobs=False, broken=True)
        app = FastAPI()
        async with lifespan_module.lifespan(app):
            assert app.state.job_worker is None
            assert app.state.multimodal_loader.is_loaded is False
            assert app.state.embedding_service and app.state.nli_service and app.state.photocard_storage
    assert events[-1] == "engine.dispose"
