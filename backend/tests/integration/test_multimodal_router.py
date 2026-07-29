from __future__ import annotations

import io
import uuid
import numpy as np
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient


def _make_fake_response(prediction: str = "FAKE", is_cached: bool = False):
    from app.features.multimodal.schemas import MultimodalPredictionResponse

    return MultimodalPredictionResponse(
        prediction_id=str(uuid.uuid4()),
        prediction=prediction,
        confidence_fake=0.82 if prediction == "FAKE" else 0.18,
        confidence_real=0.18 if prediction == "FAKE" else 0.82,
        is_cached=is_cached,
        original_id=str(uuid.uuid4()) if is_cached else None,
        similarity_scores=(
            {
                "text_similarity": 0.95,
                "image_similarity": 0.88,
                "combined_similarity": 0.92,
            }
            if is_cached
            else None
        ),
        minio_object_key="multimodal/abc/test.jpg",
        model_version="banglabert_efficientnetb4_v1",
        created_at=datetime.now(timezone.utc),
    )


def _make_test_app():
    from app.main import create_app

    app = create_app()

    mock_loader = MagicMock()
    mock_loader.is_loaded = True

    mock_storage = MagicMock()

    app.state.multimodal_loader = mock_loader
    app.state.multimodal_storage = mock_storage

    return app


class TestMultimodalPredictEndpoint:

    def _make_image_bytes(self) -> bytes:
        import struct, zlib

        def png_chunk(tag, data):
            c = struct.pack(">I", len(data)) + tag + data
            return c + struct.pack(">I", zlib.crc32(c[4:]) & 0xFFFFFFFF)

        ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
        idat = zlib.compress(b"\x00\xff\xff\xff")
        png = b"\x89PNG\r\n\x1a\n"
        png += png_chunk(b"IHDR", ihdr)
        png += png_chunk(b"IDAT", idat)
        png += png_chunk(b"IEND", b"")
        return png

    def test_predict_returns_200_with_valid_inputs(self):
        with patch(
            "app.features.multimodal.router.MultimodalPredictionService"
        ) as mock_service_cls:
            mock_service = AsyncMock()
            mock_service.predict = AsyncMock(return_value=_make_fake_response("FAKE"))
            mock_service_cls.return_value = mock_service

            app = _make_test_app()
            client = TestClient(app, raise_server_exceptions=True)

            img_bytes = self._make_image_bytes()
            response = client.post(
                "/api/v1/multimodal/predict",
                data={
                    "headline": "Test headline",
                    "body_text": "Test body text content",
                },
                files={"image": ("test.png", io.BytesIO(img_bytes), "image/png")},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["prediction"] in ("FAKE", "NON_FAKE")
        assert "confidence_fake" in data
        assert "confidence_real" in data
        assert "is_cached" in data
        assert "prediction_id" in data

    def test_predict_rejects_non_image_file(self):
        app = _make_test_app()
        client = TestClient(app, raise_server_exceptions=False)

        response = client.post(
            "/api/v1/multimodal/predict",
            data={"headline": "Test", "body_text": "Body"},
            files={"image": ("doc.pdf", io.BytesIO(b"fake pdf"), "application/pdf")},
        )
        assert response.status_code == 415

    def test_predict_rejects_empty_body_text(self):
        app = _make_test_app()
        client = TestClient(app, raise_server_exceptions=False)

        img_bytes = self._make_image_bytes()
        response = client.post(
            "/api/v1/multimodal/predict",
            data={"headline": "Test", "body_text": "short"},
            files={"image": ("img.png", io.BytesIO(img_bytes), "image/png")},
        )
        assert response.status_code == 422

    def test_predict_missing_image_returns_422(self):
        app = _make_test_app()
        client = TestClient(app, raise_server_exceptions=False)

        response = client.post(
            "/api/v1/multimodal/predict",
            data={"headline": "Test", "body_text": "Test body text content"},
        )
        assert response.status_code == 422

    def test_predict_returns_cached_flag(self):
        with patch(
            "app.features.multimodal.router.MultimodalPredictionService"
        ) as mock_service_cls:
            mock_service = AsyncMock()
            mock_service.predict = AsyncMock(
                return_value=_make_fake_response("NON_FAKE", is_cached=True)
            )
            mock_service_cls.return_value = mock_service

            app = _make_test_app()
            client = TestClient(app, raise_server_exceptions=True)

            img_bytes = self._make_image_bytes()
            response = client.post(
                "/api/v1/multimodal/predict",
                data={"headline": "Test", "body_text": "Test body text content"},
                files={"image": ("img.png", io.BytesIO(img_bytes), "image/png")},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["is_cached"] is True
        assert data["original_id"] is not None
        assert data["similarity_scores"] is not None
