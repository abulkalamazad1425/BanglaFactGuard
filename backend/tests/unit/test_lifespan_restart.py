"""App lifespan: startup -> shutdown -> startup in one process, with the
shutdown order workers -> clients -> DB engine. External services (Redis,
MinIO, models, workers) are faked; the lifespan code itself is real."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


class _Worker:
    def __init__(self, name, events, *args, **kwargs):
        self.name, self.events = name, events

    def start(self):
        self.events.append(f"{self.name}.start")

    async def stop(self):
        self.events.append(f"{self.name}.stop")


@pytest.mark.asyncio
async def test_lifespan_can_start_twice_and_disposes_engine_after_workers():
    from app.core import lifespan as lifespan_module

    events: list[str] = []
    settings = lifespan_module._SETTINGS
    redis_client = MagicMock(aclose=AsyncMock(side_effect=lambda: events.append("redis.close")))

    def storage(*_a, **_k):
        return MagicMock(ensure_bucket=AsyncMock())

    with (
        patch.object(settings.ml, "load_models_on_startup", False),
        patch.object(settings.multimodal, "load_on_startup", False),
        patch.object(settings.jobs, "enabled", True),
        patch.object(lifespan_module.aioredis, "from_url", return_value=redis_client),
        patch.object(lifespan_module, "MultimodalStorageService", side_effect=storage),
        patch.object(lifespan_module, "PhotoCardStorageService", side_effect=storage),
        patch(
            "app.features.verification.jobs.VerificationJobWorker",
            side_effect=lambda *a, **k: _Worker("jobs", events),
        ),
        patch("app.features.verification.jobs.JobDeps.from_app_state", return_value=SimpleNamespace()),
        patch(
            "app.features.notifications.delivery.ResultDeliveryWorker",
            side_effect=lambda *a, **k: _Worker("delivery", events),
        ),
        patch(
            "app.features.expert_review.escalation.EscalationWorker",
            side_effect=lambda *a, **k: _Worker("escalation", events),
        ),
        patch.object(
            lifespan_module, "close_engine", AsyncMock(side_effect=lambda: events.append("engine.dispose"))
        ),
    ):
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


@pytest.mark.asyncio
async def test_engine_is_usable_again_after_dispose():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with engine.connect() as conn:
            assert (await conn.execute(text("select 1"))).scalar_one() == 1
        await engine.dispose()
        async with engine.connect() as conn:  # a later startup reuses the engine
            assert (await conn.execute(text("select 1"))).scalar_one() == 1
    finally:
        await engine.dispose()
