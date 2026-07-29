
import pytest
import uuid
from unittest.mock import AsyncMock, patch

from app.core.constants import VerificationLabel

@pytest.mark.asyncio
async def test_health_endpoint(client):
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data

@pytest.mark.asyncio
async def test_readiness_endpoint(client, test_cache_service):

    test_cache_service.health_check = AsyncMock(return_value=True)

    response = await client.get("/api/v1/health/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["database"] == "ok"
    assert data["redis"] == "ok"

@pytest.mark.asyncio
async def test_verify_claim_endpoint(client):
    mock_response_payload = {
        "claim_id": str(uuid.uuid4()),
        "label": "TRUE",
        "confidence": 0.92,
        "reasoning": "Matching content found.",
        "matched_articles": [],
        "scores": {
            "semantic_similarity": 0.92,
            "entity_match": 0.90,
            "keyword_overlap": 0.85,
            "numerical_consistency": 1.0,
            "contradiction_score": 0.02,
        },
        "manipulation_flags": {
            "headline_manipulated": False,
            "body_altered": False,
            "numbers_altered": False,
            "entities_replaced": False,
        },
        "normalized_source": "prothomalo.com",
        "cached": False,
        "processing_time_ms": 120,
        "created_at": "2026-06-07T00:00:00Z"
    }


    with patch("app.features.verification.service.VerificationService.verify", new_callable=AsyncMock) as mock_verify:
        mock_verify.return_value = mock_response_payload

        payload = {
            "headline": "শেখ হাসিনা নতুন উড়ালসড়ক উদ্বোধন করলেন",
            "claimed_source": "https://prothomalo.com",
            "force_refresh": True
        }

        response = await client.post("/api/v1/verify", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        assert data["label"] == "TRUE"
        assert data["confidence"] == 0.92
        assert data["normalized_source"] == "prothomalo.com"
        mock_verify.assert_called_once()

@pytest.mark.asyncio
async def test_get_verification_result_endpoint(client):
    mock_response_payload = {
        "claim_id": str(uuid.uuid4()),
        "label": "FALSE",
        "confidence": 0.88,
        "reasoning": "Contradictory content found.",
        "matched_articles": [],
        "scores": {
            "semantic_similarity": 0.40,
            "entity_match": 0.50,
            "keyword_overlap": 0.30,
            "numerical_consistency": 1.0,
            "contradiction_score": 0.80,
        },
        "manipulation_flags": {
            "headline_manipulated": False,
            "body_altered": False,
            "numbers_altered": False,
            "entities_replaced": False,
        },
        "normalized_source": "prothomalo.com",
        "cached": True,
        "processing_time_ms": None,
        "created_at": "2026-06-07T00:00:00Z"
    }

    claim_id = uuid.uuid4()
    with patch("app.features.verification.service.VerificationService.get_result", new_callable=AsyncMock) as mock_get_result:
        mock_get_result.return_value = mock_response_payload

        response = await client.get(f"/api/v1/verify/{claim_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["label"] == "FALSE"
        mock_get_result.assert_called_once_with(claim_id)

@pytest.mark.asyncio
async def test_sources_crud_endpoints(client):
    source_id = uuid.uuid4()
    mock_source = {
        "id": str(source_id),
        "canonical_name": "dailystar.net",
        "display_name": "Daily Star",
        "aliases": ["daily star"],
        "base_url": "https://dailystar.net",
        "rss_url": None,
        "language": "en",
        "description": "English news daily",
        "is_active": True,
        "created_at": "2026-06-07T00:00:00Z",
        "updated_at": "2026-06-07T00:00:00Z"
    }


    with patch("app.features.sources.service.SourceService.get_source", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_source
        response = await client.get(f"/api/v1/sources/{source_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["canonical_name"] == "dailystar.net"
        mock_get.assert_called_once_with(source_id)


    with patch("app.features.sources.service.SourceService.create_source", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = mock_source
        create_payload = {
            "canonical_name": "dailystar.net",
            "display_name": "Daily Star",
            "aliases": ["daily star"],
            "base_url": "https://dailystar.net",
            "language": "en"
        }
        response = await client.post("/api/v1/sources", json=create_payload)
        assert response.status_code == 201
        data = response.json()
        assert data["canonical_name"] == "dailystar.net"


    with patch("app.features.sources.service.SourceService.update_source", new_callable=AsyncMock) as mock_update:
        mock_update.return_value = mock_source
        update_payload = {
            "display_name": "Daily Star Updated"
        }
        response = await client.put(f"/api/v1/sources/{source_id}", json=update_payload)
        assert response.status_code == 200


    with patch("app.features.sources.service.SourceService.delete_source", new_callable=AsyncMock) as mock_delete:
        mock_delete.return_value = None
        response = await client.delete(f"/api/v1/sources/{source_id}")
        assert response.status_code == 204
        mock_delete.assert_called_once_with(source_id)
