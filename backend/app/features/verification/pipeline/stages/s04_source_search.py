from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode

import structlog

from app.core.config import get_settings
from app.core.constants import PipelineStageID, QueryType, SearchCallOutcome, SearchProvider
from app.features.verification.analysis.decisions import search_adequate
from app.shared.utils.domains import allowed_domains_for, is_allowed_host
from app.features.verification.pipeline.context import PipelineContext
from app.features.articles.schemas import CandidateArticleSchema
from app.features.search.newsdata_client import NewsDataClient
from app.features.search.google_cse_client import GoogleCSEClient
from app.features.search.pygooglenews_client import PyGoogleNewsClient
from app.features.search.duckduckgo_client import DuckDuckGoClient
from app.features.search.internal_site_client import InternalSiteSearchClient
from app.features.cache.cache_service import CacheService
from app.shared.utils.hashing import compute_search_query_hash
from app.shared.utils.article_url_heuristics import is_probable_article

logger = structlog.get_logger(__name__)


_PROVIDER_PRIORITY: dict[SearchProvider, int] = {
    SearchProvider.INTERNAL_SITE: 0,
    SearchProvider.NEWSDATA: 1,
    SearchProvider.GOOGLE_CUSTOM_SEARCH: 2,
    SearchProvider.DDG: 3,
    SearchProvider.PY_GOOGLE_NEWS: 4,
}

_STRIP_PARAMS = frozenset(
    [
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_content",
        "utm_term",
        "fbclid",
        "gclid",
        "ref",
        "source",
        "from",
        "_ga",
        "cid",
    ]
)


@dataclass
class _CallResult:
    """Outcome of ONE provider call. A failed call is FAILED - never a
    successful empty result - so the caller's accounting cannot mistake an
    outage for "the source has nothing"."""

    provider: SearchProvider
    outcome: SearchCallOutcome
    candidates: list[CandidateArticleSchema] = field(default_factory=list)
    error: str | None = None


def _canonicalise_url(url: str) -> str:
    try:
        p = urlparse(url)

        path = re.sub(r"/amp/?$", "", p.path).rstrip("/") or "/"

        if p.query:
            qs = {
                k: v
                for k, v in parse_qs(p.query, keep_blank_values=False).items()
                # __cf_* is Cloudflare's post-challenge token: the same article
                # reached through a challenge would otherwise canonicalise to a
                # different URL and survive dedup as a duplicate candidate.
                if k.lower() not in _STRIP_PARAMS
                and not k.lower().startswith("__cf_")
            }
            query = urlencode(sorted(qs.items()), doseq=True)
        else:
            query = ""
        canonical = urlunparse(
            (
                "https",
                p.netloc.lower(),
                path,
                "",
                query,
                "",
            )
        )
        return canonical
    except Exception:
        return url


def _build_keyword_query(text: str, max_words: int) -> str:
    clean = re.sub(r"site:\S+\s*", "", text).strip()
    clean = re.sub(r"[।?!\'\"(){}\\[\\]<>،؟]", " ", clean)
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
            submission_id=str(context.submission_id) if context.submission_id else "pending",
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
            (SearchProvider.INTERNAL_SITE, self.internal_site_client),
            (SearchProvider.NEWSDATA, self.newsdata_client),
            (SearchProvider.GOOGLE_CUSTOM_SEARCH, self.google_cse_client),
            (SearchProvider.DDG, self.duckduckgo_client),
            (SearchProvider.PY_GOOGLE_NEWS, self.pygooglenews_client),
        ]

        tasks: list[tuple[SearchProvider, str, str, object]] = []

        for query_text, query_type in context.search_queries:
            for provider_enum, client in providers_with_clients:

                if not self._should_dispatch(
                    provider_enum, query_type, query_text, domain
                ):
                    continue

                adapted = self._adapt_query(
                    provider_enum, query_text, domain, query_type
                )
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

        raw = await asyncio.gather(*[t[3] for t in tasks], return_exceptions=True)

        results: list[_CallResult] = []
        for (provider_enum, _, _qt, _), item in zip(tasks, raw):
            if isinstance(item, _CallResult):
                results.append(item)
            else:  # defensive: an exception escaped _call_provider
                results.append(
                    _CallResult(provider_enum, SearchCallOutcome.FAILED, error=str(item))
                )

        self._record_outcomes(context, results)
        log.info(
            "s04_search_accounting",
            attempted=context.search_attempted,
            success=context.search_success,
            success_empty=context.search_success_empty,
            failed=context.search_errors,
            cached=context.search_cached,
            skipped=context.search_skipped,
            adequate=context.search_adequate,
        )

        allowed = allowed_domains_for(domain, source_config)
        canon_map: dict[str, tuple[int, CandidateArticleSchema]] = {}
        provider_hit_counts: dict[str, int] = {
            p.value: 0 for p, _ in providers_with_clients
        }

        for call in results:
            if call.outcome == SearchCallOutcome.FAILED:
                log.warning(
                    "s04_provider_call_failed",
                    provider=call.provider.value,
                    error=(call.error or "")[:120],
                )
                continue
            provider_enum = call.provider
            priority = _PROVIDER_PRIORITY.get(provider_enum, 99)

            for candidate in call.candidates:
                url = candidate.url

                if allowed and not is_allowed_host(urlparse(url).hostname or "", allowed):
                    continue

                if not is_probable_article(url, article_url_patterns):
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

    @staticmethod
    def _record_outcomes(context: PipelineContext, results: list[_CallResult]) -> None:
        for call in results:
            bucket = context.search_provider_outcomes.setdefault(call.provider.value, {})
            bucket[call.outcome.value] = bucket.get(call.outcome.value, 0) + 1
            if call.outcome == SearchCallOutcome.SKIPPED:
                context.search_skipped += 1
                continue
            context.search_attempted += 1
            if call.outcome == SearchCallOutcome.FAILED:
                context.search_errors += 1
            elif call.outcome == SearchCallOutcome.SUCCESS:
                context.search_success += 1
            elif call.outcome == SearchCallOutcome.SUCCESS_EMPTY:
                context.search_success_empty += 1
            elif call.outcome == SearchCallOutcome.CACHED:
                context.search_cached += 1
        thresholds = get_settings().classification
        completed = (
            context.search_success + context.search_success_empty + context.search_cached
        )
        context.search_adequate = search_adequate(
            context.search_attempted,
            completed,
            min_calls=thresholds.search_min_successful_calls,
            min_ratio=thresholds.search_min_success_ratio,
        )

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
            # KEYWORDS used to be withheld here on the assumption that the
            # web-index providers would cover it. In practice this is often
            # the only provider answering, and a keyword query is what finds
            # a story whose headline was reworded after publication — an
            # exact-headline query returns nothing for those, while the
            # keyword form found the article. Date strings inside the query
            # text remain unhelpful; the date is applied as a range instead.
            if qt == "DATE_BOUND":
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
    ) -> _CallResult:
        provider_name = provider_enum.value

        # Retrieval is date-free unless this query is explicitly DATE_BOUND.
        # Applying the claimed date to every query would hide the right
        # article whenever the claimed date is the thing that is wrong (the
        # Content MATCHED + Date MISMATCHED case).
        search_date = (
            context.published_date if query_type.upper() == "DATE_BOUND" else None
        )
        query_hash = compute_search_query_hash(provider_name, query, search_date)

        if provider_enum == SearchProvider.INTERNAL_SITE and not (
            source_config and source_config.get("internal_search_url")
        ):
            # Not configured for this outlet: skipped, not a search that ran.
            return _CallResult(provider_enum, SearchCallOutcome.SKIPPED)

        if getattr(context, "force_refresh", False):
            cached_urls = None
        else:
            cached_urls = await self._get_cached_search(provider_name, query_hash)

        if cached_urls is not None:
            log.debug("s04_cache_hit", provider=provider_name, cached_count=len(cached_urls))
            return _CallResult(
                provider_enum,
                SearchCallOutcome.CACHED,
                [
                    CandidateArticleSchema(
                        url=u,
                        title_snippet=None,
                        search_provider=provider_enum,
                        query_type=query_type,
                        position=idx + 1,
                    )
                    for idx, u in enumerate(cached_urls)
                ],
            )

        try:
            kwargs: dict = {}
            if provider_enum == SearchProvider.INTERNAL_SITE:
                kwargs["source_config"] = source_config

            entries: list[tuple[str, str]] = await client.search_entries(
                query,
                domain=domain,
                published_date=search_date,
                **kwargs,
            )
        except Exception as exc:
            err_str = str(exc)
            if "not configured" in err_str.lower():
                return _CallResult(provider_enum, SearchCallOutcome.SKIPPED, error=err_str[:120])
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
            return _CallResult(provider_enum, SearchCallOutcome.FAILED, error=err_str[:200])

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
        urls = [url for url, _ in entries]
        if urls:
            await self._cache_search_result(provider_name, query_hash, urls)
            log.debug(
                "s04_provider_success",
                provider=provider_name,
                query_type=query_type,
                result_count=len(urls),
            )
            return _CallResult(provider_enum, SearchCallOutcome.SUCCESS, candidates)
        return _CallResult(provider_enum, SearchCallOutcome.SUCCESS_EMPTY)

    async def _get_cached_search(
        self, provider: str, query_hash: str
    ) -> list[str] | None:
        try:
            return await self.cache_service.get_search_result(provider, query_hash)
        except Exception:
            return None

    async def _cache_search_result(
        self, provider: str, query_hash: str, urls: list[str]
    ) -> None:
        try:
            await self.cache_service.set_search_result(provider, query_hash, urls)
        except Exception:
            pass
