"""Text-and-image claims: accepted durably before acknowledgement, predicted
once (backbones run once, a near-identical upload reuses the earlier
prediction), and a retried job never predicts twice."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest
from sqlalchemy import func, select

from app.core.constants import MultimodalPredictionLabel, OverallVerdict, SubmissionStatus
from app.features.auth.models import User
from app.features.multimodal.models import MultimodalAnalysis
from app.features.multimodal.pipeline.inference_engine import PredictionResult
from app.features.multimodal.service import MultimodalPredictionService
from app.features.notifications.models import Notification
from app.features.submissions.models import Submission
from app.features.verification.job_repository import VerificationJobRepository
from app.features.verification.models import VerificationJob
from tests.helpers.db import add_multimodal_submission, add_user, store_vectors_as_json

TEXT, IMAGE = np.ones(768, dtype=np.float32), np.ones(1792, dtype=np.float32)


@pytest.fixture(autouse=True)
def vectors_on_sqlite(monkeypatch):
    store_vectors_as_json(monkeypatch)


def storage() -> MagicMock:
    return MagicMock(upload_image=AsyncMock(side_effect=lambda **kw: f"multimodal/{kw['submission_id']}/card.png"),
                     get_presigned_url=AsyncMock(return_value="https://img/card.png"),
                     read_image=AsyncMock(return_value=b"saved image"), delete_image=AsyncMock())


def service(session, *, image=IMAGE) -> MultimodalPredictionService:
    svc = MultimodalPredictionService(db=session, loader=MagicMock(is_loaded=True), storage=storage())
    svc._extractor.extract_all_embeddings = AsyncMock(
        return_value=(TEXT, image, svc._extractor._build_combined_embedding(TEXT, image))
    )
    svc._engine = MagicMock(predict=AsyncMock(), predict_from_features=AsyncMock(
        return_value=PredictionResult(prediction="FAKE", confidence_fake=0.82, confidence_real=0.18, raw_logits=(-1.2, 2.1))
    ))
    return svc


async def predict(svc, **kw):
    return await svc.predict(headline="শিরোনাম", body_text="বিবরণ", image_bytes=b"img", original_filename="card.png", **kw)


async def test_a_fresh_prediction_runs_the_backbones_once_and_goes_to_expert_review(session):
    user = await add_user(session, total_submissions=0)
    svc = service(session)
    response = await predict(svc, submitter_id=user.id)
    svc._engine.predict.assert_not_awaited()  # the classifier reuses the extractor's features
    text_arg, img_arg = svc._engine.predict_from_features.await_args.args
    assert text_arg is TEXT and img_arg is IMAGE
    assert (response.prediction, response.is_cached, response.similarity_scores) == (MultimodalPredictionLabel.FAKE, False, None)
    assert response.image_url == "https://img/card.png" and response.minio_object_key.endswith("card.png")
    sub = await session.get(Submission, uuid.UUID(response.submission_id))
    assert sub.status == SubmissionStatus.EXPERT_REVIEW and sub.submitter_id == user.id
    assert (await session.get(User, user.id)).total_submissions == 1


async def test_a_near_identical_upload_reuses_the_earlier_prediction(session):
    first = await predict(service(session))
    again = service(session)
    cached = await predict(again)
    again._engine.predict_from_features.assert_not_awaited()
    assert cached.is_cached and cached.original_id == first.prediction_id and cached.prediction == first.prediction
    assert set(cached.similarity_scores) == {"text_similarity", "image_similarity", "combined_similarity"}
    assert cached.submission_id != first.submission_id  # still the requester's own submission
    copy = await session.get(Submission, uuid.UUID(cached.submission_id))
    assert str(copy.duplicate_of_submission_id) == first.submission_id  # kept out of Fact Explorer and the queues
    original = await session.get(MultimodalAnalysis, uuid.UUID(first.prediction_id))
    original.expert_overall_verdict = OverallVerdict.FAKE
    third = await predict(service(session))  # may match the copy: always linked to the original
    assert third.original_id == first.prediction_id and third.expert_overall_verdict == OverallVerdict.FAKE
    assert str((await session.get(Submission, uuid.UUID(third.submission_id))).duplicate_of_submission_id) == first.submission_id
    other_image = await predict(service(session, image=np.eye(1792, dtype=np.float32)[0]))
    assert other_image.is_cached is False


async def test_acceptance_stores_the_image_submission_and_job_together(db, session):
    svc = service(session)
    row = await svc.accept_upload(headline="Claim", body_text="Body of the claim", image_bytes=b"image",
                                  original_filename="card.png", submitter_id=None)
    assert (row.status, row.processing_phase) == (SubmissionStatus.PENDING, "QUEUED")
    async with db() as fresh:  # committed before the 202 goes out
        job = await VerificationJobRepository(fresh).get_by_submission(row.id)
    assert job.kind == "MULTIMODAL" and job.payload == {"image_key": f"multimodal/{row.id}/card.png", "filename": "card.png"}
    svc._storage.delete_image.assert_not_awaited()


async def test_a_failed_acceptance_rolls_back_and_removes_the_uploaded_image(session):
    svc = service(session)
    with patch("app.features.verification.job_repository.VerificationJobRepository.enqueue",
               AsyncMock(side_effect=RuntimeError("DB unavailable"))):
        with pytest.raises(RuntimeError):
            await svc.accept_upload(headline="Claim", body_text="Body text", image_bytes=b"image",
                                    original_filename="card.png", submitter_id=None)
    svc._storage.delete_image.assert_awaited_once()
    assert (await session.execute(select(func.count()).select_from(VerificationJob))).scalar_one() == 0


async def test_processing_a_queued_upload_is_idempotent(session):
    user = await add_user(session)
    svc = service(session)
    row = await svc.accept_upload(headline=None, body_text="Body", image_bytes=b"image", original_filename="card.png",
                                  submitter_id=user.id)
    payload = {"image_key": f"multimodal/{row.id}/card.png", "filename": "card.png"}
    await svc.process_queued(row, payload)
    await svc.process_queued(row, payload)  # a retried job
    svc._storage.read_image.assert_awaited_once_with(payload["image_key"])  # the saved image, read once
    svc._storage.upload_image.assert_awaited_once()  # never uploaded again
    assert svc._engine.predict_from_features.await_count == 1
    assert (await session.get(Submission, row.id)).status == SubmissionStatus.EXPERT_REVIEW
    assert (await session.execute(select(func.count()).select_from(MultimodalAnalysis))).scalar_one() == 1
    assert (await session.execute(select(func.count()).select_from(Notification))).scalar_one() == 1


async def test_listing_reports_the_total_not_the_page_size(session):
    for n in range(3):
        await add_multimodal_submission(session, headline=f"h{n}")
    svc = service(session)
    records, total = await svc.list_predictions(limit=2, offset=0)
    assert (len(records), total) == (2, 3)
    assert (await svc.get_prediction(records[0].id)).id == records[0].id
    assert (await svc.get_prediction_by_submission(records[0].submission_id)).id == records[0].id
