
from __future__ import annotations

import asyncio
import re
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode

import structlog

from app.core.constants import PipelineStageID, QueryType, SearchProvider
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


_PROVIDER_PRIORITY: dict[SearchProvider, int] = {
    SearchProvider.INTERNAL_SITE: 0,
    SearchProvider.NEWSDATA: 1,
    SearchProvider.GOOGLE_CUSTOM_SEARCH: 2,
    SearchProvider.DDG: 3,
    SearchProvider.PY_GOOGLE_NEWS: 4,
}





_NON_ARTICLE_PATTERNS = [
    r"/tag/", r"/tags/", r"/author/", r"/feed",
    r"\.rss$", r"\.xml$", r"\.atom$",
    r"/amp/$",
    r"\?s=",
    r"#comments$",
    r"news\.google\.com/search",
    r"google\.com/search",
    r"/search\?[^/]*$",
]
_NON_ARTICLE_RE = re.compile("|".join(_NON_ARTICLE_PATTERNS))


_STRIP_PARAMS = frozenset([
    "utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term",
    "fbclid", "gclid", "ref", "source", "from", "_ga", "cid",
])


def _canonicalise_url(url: str) -> str:
    try:
        p = urlparse(url)

        path = re.sub(r"/amp/?$", "", p.path).rstrip("/") or "/"

        if p.query:
            qs = {k: v for k, v in parse_qs(p.query, keep_blank_values=False).items()
                  if k.lower() not in _STRIP_PARAMS}
            query = urlencode(sorted(qs.items()), doseq=True)
        else:
            query = ""
        canonical = urlunparse((
            "https",
            p.netloc.lower(),
            path,
            "",
            query,
            "",
        ))
        return canonical
    except Exception:
        return url


def _is_probable_article(url: str, source_patterns: list[str] | None) -> bool:
    if source_patterns:
        return any(re.search(pat, url) for pat in source_patterns)

    return not _NON_ARTICLE_RE.search(url)


def _build_keyword_query(text: str, max_words: int) -> str:
    clean = re.sub(r"site:\S+\s*", "", text).strip()
    clean = re.sub(r'[।?!\'\"(){}\\[\\]<>،؟]', " ", clean)
    clean = re.sub(r"\s+", " ", clean).strip()
    return " ".join(clean.split()[:max_words])


class SourceSearchStage:

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
        article_url_patterns: list[str] | None = (
            source_config.get("article_url_patterns") if source_config else None
        )

        providers_with_clients = [
            (SearchProvider.INTERNAL_SITE,        self.internal_site_client),
            (SearchProvider.NEWSDATA,              self.newsdata_client),
            (SearchProvider.GOOGLE_CUSTOM_SEARCH,  self.google_cse_client),
            (SearchProvider.DDG,                   self.duckduckgo_client),
            (SearchProvider.PY_GOOGLE_NEWS,        self.pygooglenews_client),
        ]


        tasks: list[tuple[SearchProvider, str, str, object]] = []

        for query_text, query_type in context.search_queries:
            for provider_enum, client in providers_with_clients:

                if not self._should_dispatch(provider_enum, query_type, query_text, domain):
                    continue

                adapted = self._adapt_query(provider_enum, query_text, domain, query_type)
                if not adapted.strip():
                    continue

                coro = self._call_provider(
                    provider_enum=provider_enum,
                    client=client,
                    query=adapted,
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
        )

        coros = [t[3] for t in tasks]
        results = await asyncio.gather(*coros, return_exceptions=True)


        canon_map: dict[str, tuple[int, CandidateArticleSchema]] = {}
        provider_hit_counts: dict[str, int] = {p.value: 0 for p, _ in providers_with_clients}

        for (provider_enum, _, query_type, _), result in zip(tasks, results):
            if isinstance(result, Exception) or not isinstance(result, list):
                continue

            priority = _PROVIDER_PRIORITY.get(provider_enum, 99)

            for candidate in result:
                url = candidate.url


                if domain:
                    clean_domain = domain.replace("www.", "").lower()
                    url_netloc = urlparse(url).netloc.replace("www.", "").lower()
                    if not (url_netloc == clean_domain or url_netloc.endswith("." + clean_domain)):
                        continue


                if not _is_probable_article(url, article_url_patterns):
                    continue


                canon = _canonicalise_url(url)
                existing = canon_map.get(canon)
                if existing is None or priority < existing[0]:
                    canon_map[canon] = (priority, candidate)
                    provider_hit_counts[provider_enum.value] = (
                        provider_hit_counts.get(provider_enum.value, 0) + 1
                    )

        all_candidates = [
            cand for _, cand in sorted(canon_map.values(), key=lambda x: x[0])
        ]

        context.candidate_urls = all_candidates

        if all_candidates:
            context.search_provider_used = all_candidates[0].search_provider


        for provider_name, count in provider_hit_counts.items():
            if count == 0:
                log.warning("s04_provider_zero_results", provider=provider_name)



        log.info(
            "s04_search_completed",
            total_candidates=len(all_candidates),
            provider_hit_counts=provider_hit_counts,
        )
        return context





    def _should_dispatch(
        self,
        provider: SearchProvider,
        query_type: str,
        query_text: str,
        domain: str | None,
    ) -> bool:
        qt = query_type.upper()

        if provider == SearchProvider.INTERNAL_SITE:

            if qt in ("DATE_BOUND", "ENTITIES"):
                return False

        if provider == SearchProvider.NEWSDATA:


            if qt in ("HEADLINE", "SITE_RESTRICTED"):
                return False

        if provider == SearchProvider.PY_GOOGLE_NEWS:


            if qt in ("KEYWORDS", "DATE_BOUND"):
                return False

        return True





    def _adapt_query(
        self,
        provider: SearchProvider,
        query: str,
        domain: str | None,
        query_type: str = "",
    ) -> str:
        content_only = re.sub(r"site:\S+\s*", "", query).strip()

        if provider == SearchProvider.INTERNAL_SITE:


            return _build_keyword_query(content_only, max_words=6)

        if provider == SearchProvider.NEWSDATA:



            kw = _build_keyword_query(content_only, max_words=7)
            return kw[:80]

        if provider == SearchProvider.PY_GOOGLE_NEWS:

            if domain:
                return f"site:{domain} {content_only}"
            return content_only











        if domain:
            return f"site:{domain} {content_only}"
        return content_only





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
        provider_name = provider_enum.value
        query_hash = compute_search_query_hash(provider_name, query)


        if getattr(context, "force_refresh", False):
            cached_urls = None
        else:
            cached_urls = await self._get_cached_search(provider_name, query_hash)

        if cached_urls is not None:
            log.debug("s04_cache_hit", provider=provider_name, cached_count=len(cached_urls))
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

        except Exception as exc:
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





    async def _get_cached_search(self, provider: str, query_hash: str) -> list[str] | None:
        try:
            return await self.cache_service.get_search_result(provider, query_hash)
        except Exception:
            return None

    async def _cache_search_result(self, provider: str, query_hash: str, urls: list[str]) -> None:
        try:
            await self.cache_service.set_search_result(provider, query_hash, urls)
        except Exception:
            pass