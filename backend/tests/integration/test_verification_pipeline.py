"""VerificationService.verify end to end over the real stages, with only the
outside world faked: search providers, the article fetch/extraction (no
network) and the ML services (conftest mocks)."""

import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.core.constants import VERIFICATION_PIPELINE_VERSION, ContentStatus, SourceStatus
from app.features.sources.repository import SourceRepository
from app.features.submissions.repository import RetrievedArticleRepository, SubmissionRepository
from app.features.verification.repository import ResultRepository
from app.features.verification.schemas import VerificationRequest
from app.features.verification.service import VerificationService


def _service(db_session, cache, embedder, ner, nli, http_client) -> VerificationService:
    return VerificationService(
        submission_repo=SubmissionRepository(db_session),
        result_repo=ResultRepository(db_session),
        article_repo=RetrievedArticleRepository(db_session),
        source_repo=SourceRepository(db_session),
        cache_service=cache,
        embedding_service=embedder,
        ner_service=ner,
        nli_service=nli,
        http_client=http_client,
    )


@pytest.mark.asyncio
async def test_full_pipeline_execution(
    db_session,
    test_cache_service,
    mock_embedding_service,
    mock_ner_service,
    mock_nli_service,
):
    headline = "শেখ হাসিনা নতুন উড়ালসড়ক উদ্বোধন করলেন"
    url = "https://prothomalo.com/article/456"

    async with httpx.AsyncClient() as http_client:
        service = _service(
            db_session, test_cache_service, mock_embedding_service,
            mock_ner_service, mock_nli_service, http_client,
        )

        async def no_fetch(context):  # S05: never touch the network
            return context

        async def fake_extract(context):  # S06 output, ranked by the real S07
            from app.core.constants import SearchProvider
            from app.features.articles.schemas import RankedArticleSchema

            context.extracted_articles = [
                RankedArticleSchema(
                    url=url,
                    title=headline,
                    body="আজ নতুন উড়ালসড়ক উদ্বোধন করেন প্রধানমন্ত্রী শেখ হাসিনা। " * 5,
                    search_provider=SearchProvider.PY_GOOGLE_NEWS,
                )
            ]
            return context

        with (
            patch(
                "app.features.search.pygooglenews_client.PyGoogleNewsClient.search_entries",
                new_callable=AsyncMock,
                return_value=[(url, headline)],
            ),
            patch(
                "app.features.search.internal_site_client.InternalSiteSearchClient.search_entries",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "app.features.verification.pipeline.stages.s05_evidence_retrieval.EvidenceRetrievalStage.execute",
                side_effect=no_fetch,
            ),
            patch(
                "app.features.verification.pipeline.stages.s06_article_extractor.ArticleExtractorStage.execute",
                side_effect=fake_extract,
            ),
        ):
            response = await service.verify(
                VerificationRequest(headline=headline, claimed_source_text="https://prothomalo.com")
            )

    assert response.source_status == SourceStatus.CONFIRMED
    assert response.content_status == ContentStatus.MATCHED  # exact title match
    assert response.confidence > 0.8
    assert response.cached is False
    assert response.overall_verdict is None
    assert response.pipeline_version == VERIFICATION_PIPELINE_VERSION
    assert [a.url for a in response.matched_articles] == [url]

    submission = await SubmissionRepository(db_session).get_by_id_or_none(response.submission_id)
    assert submission is not None


@pytest.mark.asyncio
async def test_pipeline_cache_hit(
    db_session,
    test_cache_service,
    mock_redis,
    mock_embedding_service,
    mock_ner_service,
    mock_nli_service,
):
    """A Redis pointer to an earlier, complete, identical verification is
    re-validated against the database and its result is copied onto the
    requester's own submission; the search stages never run."""
    from tests.unit.db_helpers import add_completed_submission

    headline = "নতুন সেতুর উদ্বোধন হলো আজ রাজধানীতে"
    original, original_result = await add_completed_submission(
        db_session, headline=headline, submitter_id=None
    )
    mock_redis.get = AsyncMock(
        return_value=json.dumps(
            {
                "submission_id": str(original.id),
                "pipeline_version": VERIFICATION_PIPELINE_VERSION,
                "source_status": "CONFIRMED",
            }
        ).encode()
    )

    async with httpx.AsyncClient() as http_client:
        service = _service(
            db_session, test_cache_service, mock_embedding_service,
            mock_ner_service, mock_nli_service, http_client,
        )
        with patch(
            "app.features.verification.pipeline.stages.s03_query_generator.QueryGeneratorStage.execute"
        ) as mock_s03:
            response = await service.verify(
                VerificationRequest(headline=headline, claimed_source_text="https://prothomalo.com")
            )

    mock_s03.assert_not_called()
    assert response.cached is True
    assert response.submission_id != original.id  # the requester's own submission
    assert response.source_status == SourceStatus.CONFIRMED
    assert response.content_status == ContentStatus.MATCHED
    assert response.confidence == original_result.confidence

    copy = await SubmissionRepository(db_session).get_by_id(response.submission_id)
    assert copy.duplicate_of_submission_id == original.id
