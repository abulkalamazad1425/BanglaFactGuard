import pytest
import uuid
import json
from unittest.mock import AsyncMock, patch

from app.features.verification.schemas import VerificationRequest
from app.features.verification.service import VerificationService
from app.core.constants import VerificationLabel, ClaimStatus
from app.features.verification.repository import ClaimRepository
from app.features.verification.repository import ResultRepository
from app.features.articles.repository import ArticleRepository
from app.features.sources.repository import SourceRepository


@pytest.mark.asyncio
async def test_full_pipeline_execution(
    db_session,
    test_cache_service,
    mock_embedding_service,
    mock_ner_service,
    mock_nli_service,
):
    claim_repo = ClaimRepository(db_session)
    result_repo = ResultRepository(db_session)
    article_repo = ArticleRepository(db_session)
    source_repo = SourceRepository(db_session)

    from app.features.search.newsdata_client import NewsDataClient
    from app.features.search.google_cse_client import GoogleCSEClient
    from app.features.search.duckduckgo_client import DuckDuckGoClient
    import httpx

    async with httpx.AsyncClient() as http_client:
        service = VerificationService(
            claim_repo=claim_repo,
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
            claimed_source="https://prothomalo.com",
            news_body=None,
            published_date=None,
            force_refresh=True,
        )

        with (
            patch(
                "app.features.search.newsdata_client.NewsDataClient.search_entries",
                new_callable=AsyncMock,
            ) as mock_newsdata,
            patch(
                "app.features.search.google_cse_client.GoogleCSEClient.search_entries",
                new_callable=AsyncMock,
            ) as mock_google,
            patch(
                "app.features.search.duckduckgo_client.DuckDuckGoClient.search_entries",
                new_callable=AsyncMock,
            ) as mock_ddg,
            patch(
                "app.features.verification.pipeline.stages.s06_article_extractor.ArticleExtractorStage.execute"
            ) as mock_extract,
        ):
            mock_newsdata.return_value = [
                (
                    "https://prothomalo.com/article/456",
                    "শেখ হাসিনা নতুন উড়ালসড়ক উদ্বোধন করলেন",
                )
            ]
            mock_google.return_value = []
            mock_ddg.return_value = []

            async def dummy_extract_exec(context):
                from app.features.articles.schemas import RankedArticleSchema
                from app.core.constants import SearchProvider

                context.ranked_articles = [
                    RankedArticleSchema(
                        url="https://prothomalo.com/article/456",
                        title="শেখ হাসিনা নতুন উড়ালসড়ক উদ্বোধন করলেন",
                        body="আজ নতুন উড়ালসড়ক উদ্বোধন করেন প্রধানমন্ত্রী।",
                        rank_score=0.95,
                        search_provider=SearchProvider.NEWSDATA,
                    )
                ]
                return context

            mock_extract.side_effect = dummy_extract_exec

            response = await service.verify(request_payload)

            assert response.label == VerificationLabel.TRUE
            assert response.confidence > 0.8
            assert response.cached is False

            claim = await claim_repo.get_completed_by_hash(response.claim_id)
            assert claim is not None or response.claim_id is not None


@pytest.mark.asyncio
async def test_pipeline_cache_hit(
    db_session,
    test_cache_service,
    mock_embedding_service,
    mock_ner_service,
    mock_nli_service,
):
    claim_repo = ClaimRepository(db_session)
    result_repo = ResultRepository(db_session)
    article_repo = ArticleRepository(db_session)
    source_repo = SourceRepository(db_session)

    claim_hash = "f35a646c2eb5387b328a9b3a0bb21897e930bc22998a442e97a3eb17b7a0d1e2"
    cached_payload = {
        "label": "TRUE",
        "confidence": 0.94,
        "reasoning": "Cached reason",
        "scores": {
            "semantic_similarity": 0.91,
            "entity_match": 0.85,
            "keyword_overlap": 0.78,
            "numerical_consistency": 1.0,
            "contradiction_score": 0.04,
        },
        "manipulation_flags": {
            "headline_manipulated": False,
            "body_altered": False,
            "numbers_altered": False,
            "entities_replaced": False,
        },
        "matched_articles": [],
        "claim_id": str(uuid.uuid4()),
        "normalized_source": "prothomalo.com",
    }

    await test_cache_service.set_claim_result(claim_hash, json.dumps(cached_payload))

    import httpx

    async with httpx.AsyncClient() as http_client:
        service = VerificationService(
            claim_repo=claim_repo,
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
            claimed_source="https://prothomalo.com",
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

                assert response.label == VerificationLabel.TRUE
                assert response.confidence == 0.94
                assert response.cached is True

                mock_s03.assert_not_called()
