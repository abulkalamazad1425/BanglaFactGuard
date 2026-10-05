import pytest
import json
from unittest.mock import AsyncMock, patch

from app.features.verification.schemas import VerificationRequest
from app.features.verification.service import VerificationService
from app.core.constants import ContentStatus, SourceStatus
from app.features.submissions.repository import (
    RetrievedArticleRepository,
    SubmissionRepository,
)
from app.features.verification.repository import ResultRepository
from app.features.sources.repository import SourceRepository


@pytest.mark.asyncio
async def test_full_pipeline_execution(
    db_session,
    test_cache_service,
    mock_embedding_service,
    mock_ner_service,
    mock_nli_service,
):
    submission_repo = SubmissionRepository(db_session)
    result_repo = ResultRepository(db_session)
    article_repo = RetrievedArticleRepository(db_session)
    source_repo = SourceRepository(db_session)

    import httpx

    async with httpx.AsyncClient() as http_client:
        service = VerificationService(
            submission_repo=submission_repo,
            result_repo=result_repo,
            article_repo=article_repo,
            source_repo=source_repo,
            cache_service=test_cache_service,
            embedding_service=mock_embedding_service,
            ner_service=mock_ner_service,
            nli_service=mock_nli_service,
            http_client=http_client,
        )

        request_payload = VerificationRequest(
            headline="শেখ হাসিনা নতুন উড়ালসড়ক উদ্বোধন করলেন",
            claimed_source_text="https://prothomalo.com",
            body_text=None,
            published_date=None,
            force_refresh=True,
        )

        with (
            patch(
                "app.features.search.pygooglenews_client.PyGoogleNewsClient.search_entries",
                new_callable=AsyncMock,
            ) as mock_pgn,
            patch(
                "app.features.search.internal_site_client.InternalSiteSearchClient.search_entries",
                new_callable=AsyncMock,
            ) as mock_internal,
            patch(
                "app.features.verification.pipeline.stages.s06_article_extractor.ArticleExtractorStage.execute"
            ) as mock_extract,
        ):
            mock_pgn.return_value = [
                (
                    "https://prothomalo.com/article/456",
                    "শেখ হাসিনা নতুন উড়ালসড়ক উদ্বোধন করলেন",
                )
            ]
            mock_internal.return_value = []

            async def dummy_extract_exec(context):
                from app.features.articles.schemas import RankedArticleSchema
                from app.core.constants import SearchProvider

                context.ranked_articles = [
                    RankedArticleSchema(
                        url="https://prothomalo.com/article/456",
                        title="শেখ হাসিনা নতুন উড়ালসড়ক উদ্বোধন করলেন",
                        body="আজ নতুন উড়ালসড়ক উদ্বোধন করেন প্রধানমন্ত্রী।",
                        rank_score=0.95,
                        search_provider=SearchProvider.PY_GOOGLE_NEWS,
                    )
                ]
                return context

            mock_extract.side_effect = dummy_extract_exec

            response = await service.verify(request_payload)

            assert response.source_status == SourceStatus.CONFIRMED
            assert response.content_status == ContentStatus.MATCHED
            assert response.confidence > 0.8
            assert response.cached is False
            assert response.submission_id is not None

            submission = await submission_repo.get_by_id_or_none(response.submission_id)
            assert submission is not None


@pytest.mark.asyncio
async def test_pipeline_cache_hit(
    db_session,
    test_cache_service,
    mock_embedding_service,
    mock_ner_service,
    mock_nli_service,
):
    submission_repo = SubmissionRepository(db_session)
    result_repo = ResultRepository(db_session)
    article_repo = RetrievedArticleRepository(db_session)
    source_repo = SourceRepository(db_session)

    claim_hash = "f35a646c2eb5387b328a9b3a0bb21897e930bc22998a442e97a3eb17b7a0d1e2"
    cached_payload = {
        "source_status": "CONFIRMED",
        "content_status": "MATCHED",
        "date_status": None,
        "confidence": 0.94,
        "reasoning": "Cached reason",
        "headline_check_status": "COMPLETED",
        "matched_articles": [],
        "submission_id": None,
        "normalized_source": "prothomalo.com",
    }

    await test_cache_service.set_claim_result(claim_hash, json.dumps(cached_payload))

    import httpx

    async with httpx.AsyncClient() as http_client:
        service = VerificationService(
            submission_repo=submission_repo,
            result_repo=result_repo,
            article_repo=article_repo,
            source_repo=source_repo,
            cache_service=test_cache_service,
            embedding_service=mock_embedding_service,
            ner_service=mock_ner_service,
            nli_service=mock_nli_service,
            http_client=http_client,
        )

        request_payload = VerificationRequest(
            headline="শেখ হাসিনা নতুন উড়ালসড়ক উদ্বোধন করলেন",
            claimed_source_text="https://prothomalo.com",
            force_refresh=False,
        )

        with patch(
            "app.features.verification.pipeline.stages.s01_normalizer.compute_claim_hash"
        ) as mock_hash:
            mock_hash.return_value = claim_hash

            with patch(
                "app.features.verification.pipeline.stages.s03_query_generator.QueryGeneratorStage.execute"
            ) as mock_s03:
                response = await service.verify(request_payload)

                assert response.source_status == SourceStatus.CONFIRMED
                assert response.content_status == ContentStatus.MATCHED
                assert response.confidence == 0.94
                assert response.cached is True

                mock_s03.assert_not_called()
