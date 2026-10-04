"""Extension acceptance must survive panel closure and job retry."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.constants import SubmissionStatus
from app.features.multimodal.service import MultimodalPredictionService


def service():
    db = AsyncMock()
    storage = AsyncMock()
    storage.upload_image.return_value = "multimodal/one/card.png"
    svc = MultimodalPredictionService(db=db, loader=MagicMock(), storage=storage)
    svc._submissions = AsyncMock()
    svc._repo = AsyncMock()
    return svc


@pytest.mark.asyncio
async def test_accept_commits_image_submission_and_job_before_acknowledgement():
    svc = service()
    with patch("app.features.verification.job_repository.VerificationJobRepository") as cls:
        queue = cls.return_value
        queue.enqueue = AsyncMock()
        row = await svc.accept_upload(headline="Claim", body_text="Body of the claim", image_bytes=b"image", original_filename="card.png", submitter_id=None)
    assert row.status == SubmissionStatus.PENDING
    assert row.processing_phase == "QUEUED"
    queue.enqueue.assert_awaited_once_with(row.id, "MULTIMODAL", payload={"image_key": "multimodal/one/card.png", "filename": "card.png"})
    svc._db.commit.assert_awaited_once()
    svc._storage.delete_image.assert_not_awaited()


@pytest.mark.asyncio
async def test_queue_failure_rolls_back_and_removes_uploaded_object():
    svc = service()
    with patch("app.features.verification.job_repository.VerificationJobRepository") as cls:
        cls.return_value.enqueue = AsyncMock(side_effect=RuntimeError("DB unavailable"))
        with pytest.raises(RuntimeError):
            await svc.accept_upload(headline="Claim", body_text="Body text", image_bytes=b"image", original_filename="card.png", submitter_id=None)
    svc._db.rollback.assert_awaited_once()
    svc._db.commit.assert_not_awaited()
    svc._storage.delete_image.assert_awaited_once_with("multimodal/one/card.png")


@pytest.mark.asyncio
async def test_processing_reuses_accepted_submission_and_saved_image():
    svc = service()
    row = SimpleNamespace(id=uuid.uuid4(), headline="Claim", body_text="Body", submitter_id=None)
    svc._repo.get_by_submission_id.return_value = None
    svc._storage.read_image.return_value = b"saved image"
    svc.predict = AsyncMock()
    await svc.process_queued(row, {"image_key": "saved/key", "filename": "card.png"})
    assert svc.predict.await_args.kwargs["existing_submission"] is row
    assert svc.predict.await_args.kwargs["stored_image_key"] == "saved/key"
    svc._submissions.mark_ai_done.assert_awaited_once_with(row.id)
    svc._submissions.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_retry_with_stored_analysis_does_not_run_model_or_create_another_analysis():
    svc = service()
    row = SimpleNamespace(id=uuid.uuid4(), submitter_id=None)
    svc._repo.get_by_submission_id.return_value = object()
    svc.predict = AsyncMock()
    await svc.process_queued(row, {})
    svc.predict.assert_not_awaited()
    svc._storage.read_image.assert_not_awaited()
    svc._submissions.mark_ai_done.assert_awaited_once_with(row.id)


def api_client():
    from app.features.multimodal.router import router, get_async_session, get_current_user_optional
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.state.multimodal_loader = SimpleNamespace(is_loaded=True)
    app.state.multimodal_storage = object()
    app.state.job_worker = MagicMock()

    async def db():
        yield AsyncMock()

    app.dependency_overrides[get_async_session] = db
    app.dependency_overrides[get_current_user_optional] = lambda: None
    return TestClient(app), app


def test_async_endpoint_returns_202_and_wakes_worker_without_inference():
    client, app = api_client()
    row = SimpleNamespace(id=uuid.uuid4(), status=SubmissionStatus.PENDING)
    with patch("app.features.multimodal.router.MultimodalPredictionService") as cls:
        cls.return_value.accept_upload = AsyncMock(return_value=row)
        response = client.post("/api/v1/multimodal/predict/async", data={"headline": "Claim", "body_text": "The body of this claim"}, files={"image": ("card.png", b"image", "image/png")})
        cls.return_value.predict.assert_not_called()
    assert response.status_code == 202
    assert response.json()["submission_id"] == str(row.id)
    app.state.job_worker.wake.assert_called_once()


@pytest.mark.parametrize("body,mime,expected", [("          ", "image/png", 422), ("Valid article body", "application/pdf", 415)])
def test_invalid_inputs_are_rejected_before_acceptance(body, mime, expected):
    client, _ = api_client()
    with patch("app.features.multimodal.router.MultimodalPredictionService") as cls:
        response = client.post("/api/v1/multimodal/predict/async", data={"headline": "Claim", "body_text": body}, files={"image": ("file", b"data", mime)})
        cls.assert_not_called()
    assert response.status_code == expected


@pytest.mark.asyncio
async def test_durable_worker_dispatch_uses_original_submission_and_retry_is_noop(tmp_path, monkeypatch):
    """Real DB queue/submission/analysis persistence; only model/storage are faked."""
    from sqlalchemy import JSON, func, select
    import numpy as np
    from db_helpers import make_session_factory
    from app.features.multimodal.models import MultimodalAnalysis
    from app.features.submissions.models import Submission
    from app.features.verification.job_repository import VerificationJobRepository
    from app.features.verification.jobs import JobDeps, execute_job
    from app.features.multimodal.pipeline.inference_engine import PredictionResult

    engine, factory = await make_session_factory(str(tmp_path / "multimodal-worker.db"))
    # SQLite has no PostgreSQL ARRAY type. Use test-only JSON columns for vectors.
    for name in ("text_embedding", "image_embedding", "combined_embedding"):
        monkeypatch.setattr(MultimodalAnalysis.__table__.c[name], "type", JSON())
    async with engine.begin() as connection:
        await connection.run_sync(lambda c: MultimodalAnalysis.__table__.create(c))
    storage = AsyncMock()
    storage.upload_image.return_value = "multimodal/accepted/card.png"
    storage.read_image.return_value = b"image"
    storage.get_presigned_url.return_value = "https://images.example/card.png"
    loader = SimpleNamespace(is_loaded=True)
    try:
        async with factory() as session:
            svc = MultimodalPredictionService(db=session, loader=loader, storage=storage)
            row = await svc.accept_upload(headline="Claim", body_text="Article body", image_bytes=b"image", original_filename="card.png", submitter_id=None)
            sid = row.id
        async with factory() as session:
            job = await VerificationJobRepository(session).get_by_submission(sid)
            assert job.kind == "MULTIMODAL"
            payload = job.payload
            assert (await session.get(Submission, sid)).status == SubmissionStatus.PENDING
        deps = JobDeps(*(MagicMock() for _ in range(5)), multimodal_loader=loader, multimodal_storage=storage)
        with patch("app.features.multimodal.service.MultimodalEmbeddingExtractor") as extractor, patch("app.features.multimodal.service.MultimodalInferenceEngine") as inference:
            extractor.return_value.extract_all_embeddings = AsyncMock(return_value=(np.array([1.0]), np.array([1.0]), np.array([1.0])))
            inference.return_value.predict = AsyncMock(return_value=PredictionResult(prediction="FAKE", confidence_fake=0.8, confidence_real=0.2, raw_logits=(1.0, 0.0)))
            await execute_job(kind="MULTIMODAL", submission_id=sid, payload=payload, deps=deps, session_factory=factory)
            await execute_job(kind="MULTIMODAL", submission_id=sid, payload=payload, deps=deps, session_factory=factory)
            inference.return_value.predict.assert_awaited_once()
        async with factory() as session:
            assert (await session.get(Submission, sid)).status == SubmissionStatus.EXPERT_REVIEW
            assert await session.scalar(select(func.count()).select_from(Submission)) == 1
            assert await session.scalar(select(func.count()).select_from(MultimodalAnalysis)) == 1
    finally:
        await engine.dispose()
