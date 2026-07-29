from __future__ import annotations

import uuid
import numpy as np
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone


def _make_fake_record(
    prediction: str = "FAKE",
    confidence_fake: float = 0.85,
    confidence_real: float = 0.15,
    is_duplicate_of_id=None,
):
    record = MagicMock()
    record.id = uuid.uuid4()
    record.headline = "Test headline"
    record.body_text = "Test body text"
    record.minio_object_key = "multimodal/abc/test.jpg"
    record.prediction = prediction
    record.confidence_fake = confidence_fake
    record.confidence_real = confidence_real
    record.is_duplicate_of_id = is_duplicate_of_id
    record.model_version = "banglabert_efficientnetb4_v1"
    record.created_at = datetime.now(timezone.utc)
    record.updated_at = datetime.now(timezone.utc)
    record.text_embedding = list(np.ones(768, dtype=np.float32))
    record.image_embedding = list(np.ones(1792, dtype=np.float32))
    record.combined_embedding = list(np.ones(2560, dtype=np.float32))
    return record


class TestMultimodalPredictionService:

    def _make_service(self, *, duplicate_record=None):
        from app.features.multimodal.service import MultimodalPredictionService

        db = AsyncMock()
        loader = MagicMock()
        loader.is_loaded = True
        storage = AsyncMock()
        storage.upload_image = AsyncMock(return_value="multimodal/abc/test.jpg")

        service = MultimodalPredictionService(db=db, loader=loader, storage=storage)

        text_emb = np.ones(768, dtype=np.float32)
        img_emb = np.ones(1792, dtype=np.float32)
        combined_emb = np.ones(2560, dtype=np.float32)
        service._extractor = AsyncMock()
        service._extractor.extract_all_embeddings = AsyncMock(
            return_value=(text_emb, img_emb, combined_emb)
        )
        service._extractor.is_duplicate = MagicMock(
            return_value=(
                duplicate_record is not None,
                (
                    {
                        "text_similarity": 0.99,
                        "image_similarity": 0.97,
                        "combined_similarity": 0.98,
                    }
                    if duplicate_record
                    else {}
                ),
            )
        )

        fresh_record = _make_fake_record(prediction="FAKE")
        service._repo = AsyncMock()
        service._repo.find_similar_candidates = AsyncMock(
            return_value=[duplicate_record] if duplicate_record else []
        )
        service._repo.create = AsyncMock(return_value=fresh_record)

        from app.features.multimodal.pipeline.inference_engine import PredictionResult

        infer_result = PredictionResult(
            prediction="FAKE",
            confidence_fake=0.82,
            confidence_real=0.18,
            raw_logits=(-1.2, 2.1),
        )
        service._engine = AsyncMock()
        service._engine.predict = AsyncMock(return_value=infer_result)

        return service, fresh_record, duplicate_record

    @pytest.mark.asyncio
    async def test_fresh_inference_called_when_no_duplicate(self):
        service, fresh_record, _ = self._make_service(duplicate_record=None)

        response = await service.predict(
            headline="Test headline",
            body_text="Test body",
            image_bytes=b"fake_image_bytes",
            original_filename="test.jpg",
        )

        service._engine.predict.assert_called_once()
        assert response.is_cached is False
        assert response.prediction == fresh_record.prediction

    @pytest.mark.asyncio
    async def test_inference_skipped_on_cache_hit(self):
        duplicate = _make_fake_record(
            prediction="NON_FAKE", confidence_fake=0.1, confidence_real=0.9
        )
        service, _, _ = self._make_service(duplicate_record=duplicate)

        response = await service.predict(
            headline="Test headline",
            body_text="Test body",
            image_bytes=b"fake_image_bytes",
            original_filename="test.jpg",
        )

        service._engine.predict.assert_not_called()
        assert response.is_cached is True
        assert response.original_id == str(duplicate.id)

    @pytest.mark.asyncio
    async def test_image_always_uploaded_to_minio(self):
        duplicate = _make_fake_record()
        service, _, _ = self._make_service(duplicate_record=duplicate)

        await service.predict(
            headline="Test headline",
            body_text="Test body",
            image_bytes=b"fake_image_bytes",
            original_filename="test.jpg",
        )

        service._storage.upload_image.assert_called_once()

    @pytest.mark.asyncio
    async def test_response_contains_similarity_scores_on_cache_hit(self):
        duplicate = _make_fake_record()
        service, _, _ = self._make_service(duplicate_record=duplicate)

        response = await service.predict(
            headline="Test",
            body_text="Body",
            image_bytes=b"img",
            original_filename="img.jpg",
        )

        assert response.similarity_scores is not None
        assert "text_similarity" in response.similarity_scores
        assert "image_similarity" in response.similarity_scores
        assert "combined_similarity" in response.similarity_scores

    @pytest.mark.asyncio
    async def test_similarity_scores_none_on_fresh_inference(self):
        service, _, _ = self._make_service(duplicate_record=None)

        response = await service.predict(
            headline="Test",
            body_text="Body",
            image_bytes=b"img",
            original_filename="img.jpg",
        )

        assert response.similarity_scores is None
