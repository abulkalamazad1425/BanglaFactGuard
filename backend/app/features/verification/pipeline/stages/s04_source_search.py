"""
app/pipelines/stages/s04_source_search.py
==========================================
Stage 4: Source-Constrained Search

## Responsibility

Execute the generated queries (from Stage 3) against the claimed source domain
using the provider chain: NewsData.io -> Google Custom Search -> PyGoogleNews.

## Provider chain strategy

For each query variant, providers are tried in priority order:
1. **NewsData.io** (Primary, local BD news coverage, API key required)
2. **Google Custom Search API** (Secondary, high quality JSON API, API key required)
3. **PyGoogleNews** (Tertiary fallback, RSS feed scraping, no key required)

A provider is tried for the current query only if:
- All higher-priority providers returned zero results for that query, OR
- The higher-priority provider raised an error.

## URL deduplication

All result URLs from all queries and all providers are deduplicated using
a shared `seen` set. The final `context.candidate_urls` list is ordered
by first appearance (highest-priority provider, highest-priority query).

## Criticality: NON-CRITICAL
Zero results from all providers across all queries -> context.candidate_urls
is empty. Stage 5 will then produce zero articles, which Stage 11 will
classify as NOT_FOUND_IN_CLAIMED_SOURCE. The pipeline continues.

## Search result caching

Each (provider, query_hash) pair is checked against Redis before calling
the provider API. Cache writes happen after successful searches. This avoids
redundant API calls when the same claim is re-verified within the TTL window.
"""

from __future__ import annotations

import asyncio
import structlog

from app.core.constants import PipelineStageID, QueryType, SearchProvider
from app.core.exceptions import SearchError
from app.features.verification.pipeline.context import PipelineContext
from app.features.articles.schemas import CandidateArticleSchema
from app.features.search.newsdata_client import NewsDataClient
from app.features.search.google_cse_client import GoogleCSEClient
from app.features.search.pygooglenews_client import PyGoogleNewsClient
from app.features.cache.cache_service import CacheService
from app.shared.utils.hashing import compute_search_query_hash

logger = structlog.get_logger(__name__)


class SourceSearchStage:
    """
    Stage 4: Execute source-constrained searches via NewsData -> Google CSE -> PyGoogleNews.

    Dependencies (injected via constructor):
        newsdata_client:     NewsData.io client (primary).
        google_cse_client:   Google Custom Search client (secondary).
        pygooglenews_client: PyGoogleNews RSS wrapper (fallback).
        cache_service:       For search result caching.
    """

    stage_id = PipelineStageID.S04_SOURCE_SEARCH

    def __init__(
        self,
        newsdata_client: NewsDataClient,
        google_cse_client: GoogleCSEClient,
        pygooglenews_client: PyGoogleNewsClient,
        cache_service: CacheService,
    ) -> None:
        self.newsdata_client = newsdata_client
        self.google_cse_client = google_cse_client
        self.pygooglenews_client = pygooglenews_client
        self.cache_service = cache_service

    async def execute(self, context: PipelineContext) -> PipelineContext:
        """
        Execute all generated queries against the claimed source domain.

        Args:
            context: Pipeline context with search_queries and normalized_source set.

        Returns:
            Context with candidate_urls populated as a deduplicated list
            of CandidateArticleSchema objects.
        """
        log = logger.bind(
            stage=self.stage_id.value,
            claim_id=str(context.claim_id) if context.claim_id else "pending",
            domain=context.normalized_source,
        )

        if not context.search_queries:
            context.record_stage_error(self.stage_id, "No search queries available")
            return context

        domain = context.normalized_source  # May be None if S01 couldn't resolve
        seen_urls: set[str] = set()
        all_candidates: list[CandidateArticleSchema] = []

        for query_text, query_type in context.search_queries:
            candidates = await self._search_with_fallback(
                query=query_text,
                query_type=query_type,
                domain=domain,
                context=context,
                seen_urls=seen_urls,
                log=log,
            )

            for candidate in candidates:
                if candidate.url not in seen_urls:
                    seen_urls.add(candidate.url)
                    all_candidates.append(candidate)

        context.candidate_urls = all_candidates
        log.info(
            "search_completed",
            total_candidates=len(all_candidates),
            queries_executed=len(context.search_queries),
        )
        return context

    # ------------------------------------------------------------------
    # Provider chain with caching
    # ------------------------------------------------------------------

    async def _search_with_fallback(
        self,
        *,
        query: str,
        query_type: str,
        domain: str | None,
        context: PipelineContext,
        seen_urls: set[str],
        log: structlog.BoundLogger,
    ) -> list[CandidateArticleSchema]:
        """
        Try NewsData -> Google CSE -> PyGoogleNews for a single query, returning URLs.

        Args:
            query:      The search query string.
            query_type: Query type label (for logging/caching).
            domain:     Target domain constraint (may be None).
            context:    Pipeline context (for recording errors).
            seen_urls:  Global dedup set (modified in-place).
            log:        Bound logger.

        Returns:
            List of new (not previously seen) article URLs.
        """
        providers = [
            (SearchProvider.NEWSDATA, self.newsdata_client),
            (SearchProvider.GOOGLE_CUSTOM_SEARCH, self.google_cse_client),
            (SearchProvider.PY_GOOGLE_NEWS, self.pygooglenews_client),
        ]

        for provider_enum, client in providers:
            provider_name = provider_enum.value

            # Check cache first
            query_hash = compute_search_query_hash(provider_name, query)
            cached = await self._get_cached_search(provider_name, query_hash)
            if cached is not None:
                cached_candidates = [
                    CandidateArticleSchema(
                        url=u,
                        title_snippet=None,
                        search_provider=provider_enum,
                        query_type=query_type,
                        position=index + 1,
                    )
                    for index, u in enumerate(cached)
                    if u not in seen_urls
                ]
                if cached_candidates or cached:
                    log.debug(
                        "search_cache_hit",
                        provider=provider_name,
                        query_type=query_type,
                        cached_count=len(cached),
                    )
                    context.search_provider_used = provider_name
                    return cached_candidates

            # Call provider
            try:
                # All 3 new providers implement search_entries which returns (url, title)
                entries = await client.search_entries(
                    query,
                    domain=domain,
                    published_date=context.published_date,
                )
                
                urls = [url for url, _ in entries]
                candidates = [
                    CandidateArticleSchema(
                        url=url,
                        title_snippet=title,
                        search_provider=provider_enum,
                        query_type=query_type,
                        position=index + 1,
                    )
                    for index, (url, title) in enumerate(entries)
                ]

                if urls:
                    # Cache successful results
                    await self._cache_search_result(provider_name, query_hash, urls)
                    context.search_provider_used = provider_name
                    log.debug(
                        "search_provider_succeeded",
                        provider=provider_name,
                        query_type=query_type,
                        result_count=len(urls),
                    )
                    return [candidate for candidate in candidates if candidate.url not in seen_urls]

                log.debug(
                    "search_provider_empty",
                    provider=provider_name,
                    query_type=query_type,
                )
                # Zero results -> try next provider

            except Exception as exc:  # noqa: BLE001
                log.warning(
                    "search_provider_failed",
                    provider=provider_name,
                    query_type=query_type,
                    error=str(exc),
                )
                context.record_stage_error(
                    self.stage_id,
                    f"{provider_name} failed for query '{query[:40]}': {exc}",
                )
                # Try next provider

        log.debug(
            "all_providers_exhausted",
            query=query[:60],
            query_type=query_type,
        )
        return []

    async def _get_cached_search(
        self, provider: str, query_hash: str
    ) -> list[str] | None:
        """
        Fetch cached search results from Redis.

        Returns:
            List of URLs from cache, or None on cache miss / error.
        """
        try:
            return await self.cache_service.get_search_result(provider, query_hash)
        except Exception:  # noqa: BLE001
            return None

    async def _cache_search_result(
        self, provider: str, query_hash: str, urls: list[str]
    ) -> None:
        """
        Write search results to Redis (fire-and-forget, non-blocking).

        Args:
            provider:   Provider name for the cache key.
            query_hash: Hash of the query string.
            urls:       URLs to cache.
        """
        try:
            await self.cache_service.set_search_result(provider, query_hash, urls)
        except Exception:  # noqa: BLE001
            pass  # Non-fatal: cache write failure never blocks the pipeline

