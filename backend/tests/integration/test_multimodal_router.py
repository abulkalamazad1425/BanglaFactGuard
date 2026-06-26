"""
tests/integration/test_multimodal_router.py
============================================
Integration-level HTTP tests for the multimodal prediction router.

These tests use FastAPI's TestClient with app state mocked so no actual
model weights or MinIO connection is required.
"""

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
        similarity_scores={"text_similarity": 0.95, "image_similarity": 0.88, "combined_similarity": 0.92} if is_cached else None,
        minio_object_key="multimodal/abc/test.jpg",
        model_version="banglabert_efficientnetb4_v1",
        created_at=datetime.now(timezone.utc),
    )


def _make_test_app():
    """Build a FastAPI test application with mocked state."""
    from app.main import create_app

    app = create_app()

    # Override lifespan by injecting mock state directly
    mock_loader = MagicMock()
    mock_loader.is_loaded = True

    mock_storage = MagicMock()

    app.state.multimodal_loader = mock_loader
    app.state.multimodal_storage = mock_storage

    return app


class TestMultimodalPredictEndpoint:
    """Tests for POST /api/v1/multimodal/predict."""

    def _make_image_bytes(self) -> bytes:
        """Generate a minimal valid 1x1 white PNG."""
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
        """Valid request should return 200 with prediction data."""
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
                data={"headline": "Test headline", "body_text": "Test body text content"},
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
        """Non-image content type should return 415."""
        app = _make_test_app()
        client = TestClient(app, raise_server_exceptions=False)

        response = client.post(
            "/api/v1/multimodal/predict",
            data={"headline": "Test", "body_text": "Body"},
            files={"image": ("doc.pdf", io.BytesIO(b"fake pdf"), "application/pdf")},
        )
        assert response.status_code == 415

    def test_predict_rejects_empty_body_text(self):
        """Empty body_text (below min_length=10) should return 422."""
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
        """Missing image field should return 422."""
        app = _make_test_app()
        client = TestClient(app, raise_server_exceptions=False)

        response = client.post(
            "/api/v1/multimodal/predict",
            data={"headline": "Test", "body_text": "Test body text content"},
        )
        assert response.status_code == 422

    def test_predict_returns_cached_flag(self):
        """Cache hit response must have is_cached=True and original_id set."""
        with patch(
            "app.features.multimodal.router.MultimodalPredictionService"
        ) as mock_service_cls:
            mock_service = AsyncMock()
            mock_service.predict = AsyncMock(return_value=_make_fake_response("NON_FAKE", is_cached=True))
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
