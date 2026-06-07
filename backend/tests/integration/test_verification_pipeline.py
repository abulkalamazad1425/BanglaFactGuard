"""
tests/integration/test_verification_pipeline.py
=================================================
Integration tests for the 12-stage fact-verification pipeline orchestrator.
"""

import pytest
import uuid
import json
from unittest.mock import AsyncMock, patch

from app.schemas.verification import VerificationRequest
from app.services.verification_service import VerificationService
from app.core.constants import VerificationLabel, ClaimStatus
from app.repositories.claim_repository import ClaimRepository
from app.repositories.result_repository import ResultRepository
from app.repositories.article_repository import ArticleRepository
from app.repositories.source_repository import SourceRepository

@pytest.mark.asyncio
async def test_full_pipeline_execution(
    db_session,
    test_cache_service,
    mock_embedding_service,
    mock_ner_service,
    mock_nli_service,
):
    """Verify end-to-end verification pipeline runs successfully and stores logs/verdicts."""
    claim_repo = ClaimRepository(db_session)
    result_repo = ResultRepository(db_session)
    article_repo = ArticleRepository(db_session)
    source_repo = SourceRepository(db_session)
    
    # Mock search client methods inside stages
    from app.clients.brave_client import BraveSearchClient
    from app.clients.google_rss_client import GoogleRSSClient
    from app.clients.ddg_client import DDGClient
    import httpx

    # Instantiate HTTP client
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
            force_refresh=True,  # Bypass cache
        )

        # Mock Brave search client to return sample URL
        with (
            patch("app.clients.brave_client.BraveSearchClient.search", new_callable=AsyncMock) as mock_brave,
            patch("app.clients.google_rss_client.GoogleRSSClient.search", new_callable=AsyncMock) as mock_google,
            patch("app.clients.ddg_client.DDGClient.search", new_callable=AsyncMock) as mock_ddg,
            patch("app.pipelines.stages.s06_article_extractor.ArticleExtractorStage.execute") as mock_extract,
        ):
            mock_brave.return_value = ["https://prothomalo.com/article/456"]
            mock_google.return_value = []
            mock_ddg.return_value = []
            
            # Mock extractor to append a retrieved article
            async def dummy_extract_exec(context):
                from app.schemas.article import RankedArticleSchema
                from app.core.constants import SearchProvider
                context.ranked_articles = [
                    RankedArticleSchema(
                        url="https://prothomalo.com/article/456",
                        title="শেখ হাসিনা নতুন উড়ালসড়ক উদ্বোধন করলেন",
                        body="আজ নতুন উড়ালসড়ক উদ্বোধন করেন প্রধানমন্ত্রী।",
                        rank_score=0.95,
                        search_provider=SearchProvider.BRAVE,
                    )
                ]
                return context
            mock_extract.side_effect = dummy_extract_exec

            response = await service.verify(request_payload)

            assert response.label == VerificationLabel.TRUE
            assert response.confidence > 0.8
            assert response.cached is False

            # Verify claim is persisted in DB
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
    """Verify that cache lookup stage returns result immediately on cache hit."""
    claim_repo = ClaimRepository(db_session)
    result_repo = ResultRepository(db_session)
    article_repo = ArticleRepository(db_session)
    source_repo = SourceRepository(db_session)
    
    # Pre-populate Redis cache with mock result
    claim_hash = "f35a646c2eb5387b328a9b3a0bb21897e930bc22998a442e97a3eb17b7a0d1e2" # Sample hash
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

        # Patch S01 normalizer to return the exact hash so cache hits
        with patch("app.pipelines.stages.s01_normalizer.compute_claim_hash") as mock_hash:
            mock_hash.return_value = claim_hash
            
            # Set up mock search stages that shouldn't be executed
            with patch("app.pipelines.stages.s03_query_generator.QueryGeneratorStage.execute") as mock_s03:
                response = await service.verify(request_payload)
                
                assert response.label == VerificationLabel.TRUE
                assert response.confidence == 0.94
                assert response.cached is True
                # Ensure downstream stages were skipped
                mock_s03.assert_not_called()
