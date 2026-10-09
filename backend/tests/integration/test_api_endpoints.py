"""HTTP-level checks of a few public endpoints against the current API
contract (status codes and response shapes). Service calls are mocked; the
database is the SQLite `db_session` from conftest."""

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.core.constants import ContentStatus, SourceStatus, SubmissionStatus
from app.features.verification.schemas import VerificationResponse


def _verification_response(**overrides) -> VerificationResponse:
    fields = dict(
        submission_id=uuid.uuid4(),
        source_status=SourceStatus.CONFIRMED,
        content_status=ContentStatus.MATCHED,
        confidence=0.92,
        reasoning="A corresponding report was found.",
        normalized_source="prothomalo.com",
        created_at=datetime(2026, 6, 7, tzinfo=timezone.utc),
    )
    fields.update(overrides)
    return VerificationResponse(**fields)


@pytest.mark.asyncio
async def test_health_endpoint(client):
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data


@pytest.mark.asyncio
async def test_readiness_endpoint(client, test_cache_service, test_engine):
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    test_cache_service.health_check = AsyncMock(return_value=True)
    sessions = async_sessionmaker(bind=test_engine, class_=AsyncSession)

    with patch("app.features.health.router.AsyncSessionLocal", sessions):
        response = await client.get("/api/v1/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "database": "ok", "redis": "ok"}


@pytest.mark.asyncio
async def test_verify_claim_endpoint(client):
    expected = _verification_response()
    with patch(
        "app.features.verification.service.VerificationService.verify",
        new_callable=AsyncMock,
        return_value=expected,
    ) as mock_verify:
        response = await client.post(
            "/api/v1/verify",
            json={
                "headline": "শেখ হাসিনা নতুন উড়ালসড়ক উদ্বোধন করলেন",
                "claimed_source_text": "https://prothomalo.com",
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["submission_id"] == str(expected.submission_id)
    assert data["source_status"] == "CONFIRMED"
    assert data["content_status"] == "MATCHED"
    assert data["confidence"] == 0.92
    assert data["normalized_source"] == "prothomalo.com"
    assert data["overall_verdict"] is None  # never set by the automated system
    mock_verify.assert_called_once()


@pytest.mark.asyncio
async def test_get_verification_result_endpoint(client):
    submission_id = uuid.uuid4()
    expected = _verification_response(
        submission_id=submission_id, source_status=SourceStatus.NOT_FOUND, content_status=None
    )
    visible = SimpleNamespace(status=SubmissionStatus.EXPERT_REVIEW, submitter_id=None)
    with (
        patch(
            "app.features.verification.service.VerificationService.get_result",
            new_callable=AsyncMock,
            return_value=expected,
        ) as mock_get_result,
        patch(
            "app.features.submissions.repository.SubmissionRepository.get_by_id_or_none",
            new_callable=AsyncMock,
            return_value=visible,
        ),
    ):
        response = await client.get(f"/api/v1/verify/{submission_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["submission_id"] == str(submission_id)
    assert data["source_status"] == "NOT_FOUND"
    mock_get_result.assert_called_once_with(submission_id)


@pytest.mark.asyncio
async def test_get_verification_result_unknown_submission_is_404(client):
    with (
        patch(
            "app.features.verification.service.VerificationService.get_result",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "app.features.submissions.repository.SubmissionRepository.get_by_id_or_none",
            new_callable=AsyncMock,
            return_value=None,
        ),
    ):
        response = await client.get(f"/api/v1/verify/{uuid.uuid4()}")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_sources_crud_endpoints(app, client):
    from app.features.sources import router as sources_router
    from app.features.sources.schemas import SourceResponseSchema

    source_id = uuid.uuid4()
    source = SourceResponseSchema(
        id=source_id,
        canonical_name="dailystar.net",
        display_name="Daily Star",
        aliases=["daily star"],
        base_url="https://dailystar.net",
        language="en",
        search_language="en",
        js_rendered=False,
        is_active=True,
        description="English news daily",
        created_at=datetime(2026, 6, 7, tzinfo=timezone.utc),
        updated_at=datetime(2026, 6, 7, tzinfo=timezone.utc),
    )
    # Write operations are admin-only.
    app.dependency_overrides[sources_router._ADMIN_ONLY] = lambda: SimpleNamespace(role="admin")

    with patch(
        "app.features.sources.service.SourceService.get_source",
        new_callable=AsyncMock,
        return_value=source,
    ) as mock_get:
        response = await client.get(f"/api/v1/sources/{source_id}")
        assert response.status_code == 200
        assert response.json()["canonical_name"] == "dailystar.net"
        mock_get.assert_called_once_with(source_id)

    with patch(
        "app.features.sources.service.SourceService.create_source",
        new_callable=AsyncMock,
        return_value=source,
    ):
        response = await client.post(
            "/api/v1/sources",
            json={
                "canonical_name": "dailystar.net",
                "display_name": "Daily Star",
                "aliases": ["daily star"],
                "base_url": "https://dailystar.net",
                "language": "en",
            },
        )
        assert response.status_code == 201
        assert response.json()["canonical_name"] == "dailystar.net"

    with patch(
        "app.features.sources.service.SourceService.update_source",
        new_callable=AsyncMock,
        return_value=source,
    ):
        response = await client.put(
            f"/api/v1/sources/{source_id}", json={"display_name": "Daily Star Updated"}
        )
        assert response.status_code == 200

    with patch(
        "app.features.sources.service.SourceService.delete_source",
        new_callable=AsyncMock,
        return_value=None,
    ) as mock_delete:
        response = await client.delete(f"/api/v1/sources/{source_id}")
        assert response.status_code == 204
        mock_delete.assert_called_once_with(source_id)


@pytest.mark.asyncio
async def test_source_write_requires_admin(client):
    response = await client.delete(f"/api/v1/sources/{uuid.uuid4()}")
    assert response.status_code == 401
