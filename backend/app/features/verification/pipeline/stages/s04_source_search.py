"""
app/pipelines/stages/s04_source_search.py
==========================================
Stage 4: Source-Constrained Search

## Responsibility

Execute ALL generated queries (from Stage 3) against ALL search providers
in true parallel using asyncio.gather, then merge and deduplicate results.

## Search Strategy

For EVERY query variant (up to MAX_SEARCH_QUERIES from Stage 3), ALL 5
providers are searched simultaneously:

    1. InternalSiteSearch  — Site's own search endpoint (highest precision)
    2. NewsData.io         — BD-focused news API (best coverage for BD sources)
    3. Google Custom Search — High-quality API results
    4. DuckDuckGo          — Free fallback, no rate limits
    5. PyGoogleNews        — Google News RSS (last resort)

## Provider-Specific Query Adaptation

Each provider receives a query variant tailored to its strengths:
  - InternalSite: Short keyword query (5 words max, no punctuation)
  - NewsData:     Short keyword query (60 char max) + domain filter
  - Google CSE:   Full site:domain headline query
  - DDG:          Full site:domain headline query
  - PyGoogleNews: Headline query (no site operator - RSS is pre-filtered)

## Result Merging

All results from all (query × provider) combinations are collected into a
single pool. Priority ordering for deduplication:
  Internal > NewsData > Google CSE > DDG > PyGoogleNews

## URL Deduplication & Domain Filtering

- Only URLs matching the claimed source domain are kept.
- Duplicate URLs (seen from multiple providers) are dropped.
- Non-article URLs (tags, categories, feeds) are filtered via NON_ARTICLE_PATTERNS.

## Criticality: NON-CRITICAL
Zero results → context.candidate_urls is empty → Stage 11 returns NOT_FOUND.
"""

from __future__ import annotations

import asyncio
import re
import structlog

from app.core.constants import PipelineStageID, QueryType, SearchProvider
from app.core.exceptions import SearchError
from app.features.verification.pipeline.context import PipelineContext
from app.features.articles.schemas import CandidateArticleSchema
from app.features.search.newsdata_client import NewsDataClient
from app.features.search.google_cse_client import GoogleCSEClient
from app.features.search.pygooglenews_client import PyGoogleNewsClient
from app.features.search.duckduckgo_client import DuckDuckGoClient
from app.features.search.internal_site_client import InternalSiteSearchClient
from app.features.cache.cache_service import CacheService
from app.shared.utils.hashing import compute_search_query_hash

logger = structlog.get_logger(__name__)

# Patterns that indicate a URL is NOT an article page
NON_ARTICLE_PATTERNS = [
    r"/video/", r"/gallery/", r"/photo/", r"/tag/", r"/tags/",
    r"/author/", r"/archive/", r"/category/", r"/feed",
    r"\.rss$", r"\.xml$", r"/amp/", r"\?s=", r"/page/\d+",
    r"news\.google\.com/search", r"google\.com/search",
    r"/search\?", r"/search/$", r"#comments",
]

# Provider priority for deduplication (lower index = higher priority)
_PROVIDER_PRIORITY: dict[SearchProvider, int] = {
    SearchProvider.INTERNAL_SITE: 0,
    SearchProvider.NEWSDATA: 1,
    SearchProvider.GOOGLE_CUSTOM_SEARCH: 2,
    SearchProvider.DDG: 3,
    SearchProvider.PY_GOOGLE_NEWS: 4,
}


def is_probable_article(url: str) -> bool:
    """Return True if the URL looks like an article (not a tag/feed/category page)."""
    for pattern in NON_ARTICLE_PATTERNS:
        if re.search(pattern, url):
            return False
    return True


def _build_keyword_query(query: str, max_words: int = 6) -> str:
    """
    Strip site: operators and punctuation, return only the top N words.
    Used for providers that prefer concise keyword queries (Internal, NewsData).
    """
    # Remove site: operator
    clean = re.sub(r'site:\S+\s*', '', query).strip()
    # Remove Bangla/English punctuation that can break search backends
    clean = re.sub(r'[।?!\'"(){}\[\]<>]', ' ', clean)
    # Collapse whitespace
    clean = re.sub(r'\s+', ' ', clean).strip()
    # Limit to max_words
    words = clean.split()
    return ' '.join(words[:max_words])


class SourceSearchStage:
    """
    Stage 4: Execute ALL queries against ALL providers in full parallel.

    Dependencies (injected via constructor):
        newsdata_client:      NewsData.io client
        google_cse_client:    Google Custom Search client
        duckduckgo_client:    DuckDuckGo scraping client
        pygooglenews_client:  PyGoogleNews RSS wrapper
        internal_site_client: Direct site search scraper
        cache_service:        Redis-backed search result cache
    """

    stage_id = PipelineStageID.S04_SOURCE_SEARCH

    def __init__(
        self,
        newsdata_client: NewsDataClient,
        google_cse_client: GoogleCSEClient,
        pygooglenews_client: PyGoogleNewsClient,
        duckduckgo_client: DuckDuckGoClient,
        internal_site_client: InternalSiteSearchClient,
        cache_service: CacheService,
    ) -> None:
        self.newsdata_client = newsdata_client
        self.google_cse_client = google_cse_client
        self.pygooglenews_client = pygooglenews_client
        self.duckduckgo_client = duckduckgo_client
        self.internal_site_client = internal_site_client
        self.cache_service = cache_service

    async def execute(self, context: PipelineContext) -> PipelineContext:
        """
        Run all search_queries × all providers in full parallel, merge results.

        Args:
            context: Pipeline context with search_queries and normalized_source set.

        Returns:
            Context with candidate_urls populated as a deduplicated, domain-filtered,
            priority-ordered list of CandidateArticleSchema objects.
        """
        log = logger.bind(
            stage=self.stage_id.value,
            claim_id=str(context.claim_id) if context.claim_id else "pending",
            domain=context.normalized_source,
        )

        if not context.search_queries:
            context.record_stage_error(self.stage_id, "No search queries available")
            return context

        domain = context.normalized_source
        source_config = getattr(context, "source_config", None)

        # Build all (query, provider) tasks upfront and run them all at once
        # Each entry: (provider_enum, query_text, query_type, coroutine)
        tasks: list[tuple[SearchProvider, str, str, asyncio.Task]] = []

        providers_with_clients = [
            (SearchProvider.INTERNAL_SITE, self.internal_site_client),
            (SearchProvider.NEWSDATA, self.newsdata_client),
            (SearchProvider.GOOGLE_CUSTOM_SEARCH, self.google_cse_client),
            (SearchProvider.DDG, self.duckduckgo_client),
            (SearchProvider.PY_GOOGLE_NEWS, self.pygooglenews_client),
        ]

        for query_text, query_type in context.search_queries:
            for provider_enum, client in providers_with_clients:
                adapted_query = self._adapt_query(provider_enum, query_text, domain, query_type)
                coro = self._call_provider(
                    provider_enum=provider_enum,
                    client=client,
                    query=adapted_query,
                    query_type=query_type,
                    domain=domain,
                    context=context,
                    source_config=source_config,
                    log=log,
                )
                tasks.append((provider_enum, query_text, query_type, coro))

        log.info(
            "s04_parallel_search_start",
            total_tasks=len(tasks),
            queries=len(context.search_queries),
            providers=len(providers_with_clients),
        )

        # Fire every task at once
        coros = [t[3] for t in tasks]
        results = await asyncio.gather(*coros, return_exceptions=True)

        # ── Merge results by provider priority ──────────────────────────────
        # Build a map: url → (priority, CandidateArticleSchema)
        # so lower-priority duplicates are discarded
        url_priority_map: dict[str, tuple[int, CandidateArticleSchema]] = {}

        for (provider_enum, _, query_type, _), result in zip(tasks, results):
            if isinstance(result, Exception):
                # Already logged inside _call_provider; skip
                continue
            if not isinstance(result, list):
                continue

            priority = _PROVIDER_PRIORITY.get(provider_enum, 99)

            for candidate in result:
                url = candidate.url

                # Domain filter: only keep URLs that belong to the claimed source.
                # Use normalized comparison: strip www., compare root domain substring.
                if domain:
                    clean_domain = domain.replace("www.", "").lower()
                    from urllib.parse import urlparse
                    url_netloc = urlparse(url).netloc.replace("www.", "").lower()
                    # Accept if the url's netloc ends with or equals the domain
                    # (handles subdomains like en.prothomalo.com)
                    if not (url_netloc == clean_domain or url_netloc.endswith("." + clean_domain)):
                        continue

                # Non-article filter
                if not is_probable_article(url):
                    continue

                # Keep if not seen, or replace if we now have a higher-priority source
                existing = url_priority_map.get(url)
                if existing is None or priority < existing[0]:
                    url_priority_map[url] = (priority, candidate)

        # Sort by provider priority (ascending) to give best-provider results first
        all_candidates = [
            cand
            for _, cand in sorted(url_priority_map.values(), key=lambda x: x[0])
        ]

        context.candidate_urls = all_candidates

        # --- DEBUG WRITE (EASY TO REMOVE) ---
        import json
        try:
            debug_path = r"E:\search_results_debug.json"
            debug_data = [{"url": c.url, "provider": c.search_provider.value, "title_snippet": c.title_snippet} for c in all_candidates]
            with open(debug_path, "w", encoding="utf-8") as f:
                json.dump(debug_data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            log.warning("debug_write_failed", error=str(e))
        # ------------------------------------

        # Track which providers actually contributed for logging
        contributing_providers = {
            cand.search_provider.value
            for cand in all_candidates
        }
        if all_candidates:
            # The DB enum only accepts a single provider, so we save the highest-priority one
            context.search_provider_used = all_candidates[0].search_provider

        log.info(
            "s04_search_completed",
            total_candidates=len(all_candidates),
            queries_executed=len(context.search_queries),
            providers_with_results=list(contributing_providers),
        )
        return context

    # ------------------------------------------------------------------
    # Query adaptation per provider
    # ------------------------------------------------------------------

    def _adapt_query(
        self,
        provider: SearchProvider,
        query: str,
        domain: str | None,
        query_type: str = "",
    ) -> str:
        """
        Return a provider-optimised variant of the query.

        Strategy:
          - INTERNAL_SITE: keyword-only, no site: operator (URL template handles domain)
          - NEWSDATA:       keyword-only (≤80 chars, API works better with shorter queries)
          - GOOGLE_CSE:     quoted phrase for SITE_RESTRICTED/HEADLINE, plain for others
          - DDG:            same as Google CSE — quotes force exact phrase matching
          - PY_GOOGLE_NEWS: strip any site: from S03, then add domain cleanly
        """
        # Strip site: from query to get the clean content portion
        content_only = re.sub(r'site:\S+\s*', '', query).strip()

        if provider == SearchProvider.INTERNAL_SITE:
            # Keyword-only: no site: operator (the URL template handles domain routing)
            return _build_keyword_query(content_only, max_words=8)

        if provider == SearchProvider.NEWSDATA:
            # NewsData performs best with short keyword queries, no site: operator
            kw = _build_keyword_query(content_only, max_words=8)
            return kw[:80]  # Hard cap at 80 chars

        if provider == SearchProvider.PY_GOOGLE_NEWS:
            # PyGoogleNews / RSS: strip site: then re-add domain cleanly
            if domain:
                return f"site:{domain} {content_only}"
            return content_only

        # Google CSE and DDG:
        # For SITE_RESTRICTED and HEADLINE queries, use exact phrase quoting.
        # This forces the search engine to find the specific article rather than
        # loosely-related articles from the same domain (e.g. other Morocco news).
        _exact_types = {"SITE_RESTRICTED", "HEADLINE"}
        if query_type.upper() in _exact_types and content_only:
            # Wrap the first ~10 words in quotes (very long phrases hurt recall)
            words = content_only.split()
            # Quote the first 8 words as the exact anchor phrase
            quoted_part = '"' + ' '.join(words[:8]) + '"'
            remainder = ' '.join(words[8:])  # Leave the tail unquoted for recall
            phrase = f"{quoted_part} {remainder}".strip()
            if domain:
                return f"site:{domain} {phrase}"
            return phrase

        # For KEYWORDS / BODY_SUMMARY / ENTITIES — no quoting (broader recall)
        if domain:
            return f"site:{domain} {content_only}"
        return content_only

    # ------------------------------------------------------------------
    # Single provider call with caching
    # ------------------------------------------------------------------

    async def _call_provider(
        self,
        *,
        provider_enum: SearchProvider,
        client,
        query: str,
        query_type: str,
        domain: str | None,
        context: PipelineContext,
        source_config: dict | None,
        log: structlog.BoundLogger,
    ) -> list[CandidateArticleSchema]:
        """
        Call a single provider for a single query with cache check/write.

        Returns a list of CandidateArticleSchema (may be empty on error or cache miss).
        Exceptions are caught and logged — never propagated.
        """
        provider_name = provider_enum.value
        query_hash = compute_search_query_hash(provider_name, query)

        # ── Cache check ──────────────────────────────────────────────────
        cached_urls = await self._get_cached_search(provider_name, query_hash)
        if cached_urls is not None:
            log.debug(
                "s04_cache_hit",
                provider=provider_name,
                query_type=query_type,
                cached_count=len(cached_urls),
            )
            return [
                CandidateArticleSchema(
                    url=u,
                    title_snippet=None,
                    search_provider=provider_enum,
                    query_type=query_type,
                    position=idx + 1,
                )
                for idx, u in enumerate(cached_urls)
            ]

        # ── Live provider call ────────────────────────────────────────────
        try:
            kwargs: dict = {}
            if provider_enum == SearchProvider.INTERNAL_SITE:
                kwargs["source_config"] = source_config

            entries: list[tuple[str, str]] = await client.search_entries(
                query,
                domain=domain,
                published_date=context.published_date,
                **kwargs,
            )

            urls = [url for url, _ in entries]
            candidates = [
                CandidateArticleSchema(
                    url=url,
                    title_snippet=title or None,
                    search_provider=provider_enum,
                    query_type=query_type,
                    position=idx + 1,
                )
                for idx, (url, title) in enumerate(entries)
            ]

            if urls:
                await self._cache_search_result(provider_name, query_hash, urls)
                log.debug(
                    "s04_provider_success",
                    provider=provider_name,
                    query_type=query_type,
                    result_count=len(urls),
                )

            return candidates

        except Exception as exc:  # noqa: BLE001
            err_str = str(exc)
            if "not configured" not in err_str.lower():
                log.warning(
                    "s04_provider_failed",
                    provider=provider_name,
                    query_type=query_type,
                    error=err_str[:120],
                )
                context.record_stage_error(
                    self.stage_id,
                    f"{provider_name} failed for '{query[:40]}': {err_str[:80]}",
                )
            return []

    # ------------------------------------------------------------------
    # Cache helpers
    # ------------------------------------------------------------------

    async def _get_cached_search(
        self, provider: str, query_hash: str
    ) -> list[str] | None:
        """Fetch cached URL list from Redis. Returns None on miss/error."""
        try:
            return await self.cache_service.get_search_result(provider, query_hash)
        except Exception:  # noqa: BLE001
            return None

    async def _cache_search_result(
        self, provider: str, query_hash: str, urls: list[str]
    ) -> None:
        """Write URL list to Redis (fire-and-forget, non-blocking)."""
        try:
            await self.cache_service.set_search_result(provider, query_hash, urls)
        except Exception:  # noqa: BLE001
            pass
