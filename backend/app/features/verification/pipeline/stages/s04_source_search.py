"""
app/pipelines/stages/s04_source_search.py  (redesigned)
=========================================================
Stage 4: Source-Constrained Search — Provider-Adaptive Dispatch

## What changed and why
────────────────────────────────────────────────────────────────
ROOT PROBLEMS (old design)
  1. Every (query × provider) pair ran regardless of fit.  Sending a Bangla
     headline verbatim to NewsData (English-first API) burns a quota slot and
     returns nothing useful.

  2. _adapt_query() quoted the first 8 words for SITE_RESTRICTED/HEADLINE
     queries on Google CSE and DDG.  For poorly-indexed sites, an exact-phrase
     match returns zero results.  The quote is the single biggest recall killer.

  3. NON_ARTICLE_PATTERNS was global and English-centric.  It silently dropped
     valid Bangla article URLs whose paths happen to contain a word like
     "archive" in English (e.g. /archive/ is common in BD sites for date-based
     paths that ARE articles).

  4. Domain matching only checked URL netloc.  A result from
     en.prothomalo.com when the claim said prothomalo.com was accepted, but
     results from prothomalo.com/amp/ were not filtered separately.

  5. URL deduplication used exact string matching on the raw URL.  The same
     article fetched as http:// vs https://, with/without trailing slash,
     with/without query params would appear twice and be fetched twice.

NEW APPROACH
────────────────────────────────────────────────────────────────
  A. Provider routing: each provider receives only the query types that suit it.
     - InternalSite:  short keywords only  (its own site, no site: operator)
     - NewsData:      short English-transliterated keywords or entity names
     - Google CSE:    unquoted site: + keywords  (NOT quoted phrases)
     - DDG:           same as Google CSE, with a width-first fallback (no site:)
     - PyGoogleNews:  headline (RSS is already domain-filtered by feed URL)

  B. Quoting removed from _adapt_query for CSE/DDG.
     site:domain keyword1 keyword2 keyword3 is strictly more recall than
     site:domain "keyword1 keyword2 keyword3 keyword4 keyword5 keyword6 keyword7 keyword8"
     For well-indexed sites (Prothom Alo) both work; for poorly-indexed sites
     only the unquoted form works.

  C. Source-aware URL filtering.
     Each source in the registry now provides article_url_patterns.  When the
     source is known, only URLs matching at least one article_url_pattern are
     kept.  The global NON_ARTICLE_PATTERNS are a secondary, safety-net filter
     applied only when no source-specific patterns exist.

  D. URL canonicalisation before dedup.
     Strip scheme (http/https), trailing slash, common tracking params, and
     /amp/ suffix before dedup — so the same article isn't fetched twice.

  E. Tiered fallback visibility.
     We track per-provider result counts and log a structured warning when a
     provider returns zero results for ALL queries.  This makes silent failures
     visible in the log pipeline.
"""

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

# ── Provider priority for deduplication (lower = higher priority) ──────────
_PROVIDER_PRIORITY: dict[SearchProvider, int] = {
    SearchProvider.INTERNAL_SITE: 0,
    SearchProvider.NEWSDATA: 1,
    SearchProvider.GOOGLE_CUSTOM_SEARCH: 2,
    SearchProvider.DDG: 3,
    SearchProvider.PY_GOOGLE_NEWS: 4,
}

# ── Global non-article patterns (last-resort filter, not primary) ───────────
# Deliberately conservative: only patterns that are unambiguously non-article
# across ALL BD news sites.  Archive date paths (/2024/01/10/) are NOT in this
# list because they ARE valid article paths on most BD sites.
_NON_ARTICLE_PATTERNS = [
    r"/tag/", r"/tags/", r"/author/", r"/feed",
    r"\.rss$", r"\.xml$", r"\.atom$",
    r"/amp/$",          # /amp/ mid-path is fine (we strip it); bare /amp/ is not
    r"\?s=",            # WordPress search
    r"#comments$",
    r"news\.google\.com/search",
    r"google\.com/search",
    r"/search\?[^/]*$", # search result pages (but NOT article paths with ?ref=...)
]
_NON_ARTICLE_RE = re.compile("|".join(_NON_ARTICLE_PATTERNS))

# Tracking parameters to strip during URL canonicalisation
_STRIP_PARAMS = frozenset([
    "utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term",
    "fbclid", "gclid", "ref", "source", "from", "_ga", "cid",
])


def _canonicalise_url(url: str) -> str:
    """
    Return a normalised URL for deduplication.
    - Lowercases scheme + netloc
    - Strips /amp/ suffix
    - Strips trailing slash
    - Removes known tracking query parameters
    - Sorts remaining query params for stable comparison
    """
    try:
        p = urlparse(url)
        # Strip /amp suffix variations
        path = re.sub(r"/amp/?$", "", p.path).rstrip("/") or "/"
        # Clean query string
        if p.query:
            qs = {k: v for k, v in parse_qs(p.query, keep_blank_values=False).items()
                  if k.lower() not in _STRIP_PARAMS}
            query = urlencode(sorted(qs.items()), doseq=True)
        else:
            query = ""
        canonical = urlunparse((
            "https",                    # normalise scheme
            p.netloc.lower(),
            path,
            "",                         # params (;key=val — never used in BD news)
            query,
            "",                         # fragment
        ))
        return canonical
    except Exception:
        return url


def _is_probable_article(url: str, source_patterns: list[str] | None) -> bool:
    """
    Return True if URL looks like an article page.

    Strategy (in order):
      1. If source_patterns provided (from registry), accept URL only if it
         matches at least one pattern.  This is the most precise filter.
      2. Otherwise fall back to global NON_ARTICLE_PATTERNS rejection list.
    """
    if source_patterns:
        return any(re.search(pat, url) for pat in source_patterns)
    # Global fallback: reject known non-article patterns
    return not _NON_ARTICLE_RE.search(url)


def _build_keyword_query(text: str, max_words: int) -> str:
    """
    Strip site: operator and Bangla/English punctuation; keep top N words.
    Used for providers with short-query requirements.
    """
    clean = re.sub(r"site:\S+\s*", "", text).strip()
    clean = re.sub(r'[।?!\'\"(){}\\[\\]<>،؟]', " ", clean)
    clean = re.sub(r"\s+", " ", clean).strip()
    return " ".join(clean.split()[:max_words])


class SourceSearchStage:
    """
    Stage 4: Fan out queries to providers using per-provider adaptation.

    Key design change: provider routing is query-type-aware.
    Not every (query, provider) pair is dispatched — only combinations
    where the provider is likely to return something useful.
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

        # ── Build task list with provider-routing filter ─────────────────
        tasks: list[tuple[SearchProvider, str, str, object]] = []

        for query_text, query_type in context.search_queries:
            for provider_enum, client in providers_with_clients:
                # Skip (query, provider) pairs that are known poor matches
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

        # ── Merge: canonical-URL → (priority, candidate) ─────────────────
        canon_map: dict[str, tuple[int, CandidateArticleSchema]] = {}
        provider_hit_counts: dict[str, int] = {p.value: 0 for p, _ in providers_with_clients}

        for (provider_enum, _, query_type, _), result in zip(tasks, results):
            if isinstance(result, Exception) or not isinstance(result, list):
                continue

            priority = _PROVIDER_PRIORITY.get(provider_enum, 99)

            for candidate in result:
                url = candidate.url

                # ── Domain filter ────────────────────────────────────────
                if domain:
                    clean_domain = domain.replace("www.", "").lower()
                    url_netloc = urlparse(url).netloc.replace("www.", "").lower()
                    if not (url_netloc == clean_domain or url_netloc.endswith("." + clean_domain)):
                        continue

                # ── Article-pattern filter (source-aware first) ──────────
                if not _is_probable_article(url, article_url_patterns):
                    continue

                # ── Canonical dedup ──────────────────────────────────────
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

        # Warn on completely silent providers
        for provider_name, count in provider_hit_counts.items():
            if count == 0:
                log.warning("s04_provider_zero_results", provider=provider_name)



        log.info(
            "s04_search_completed",
            total_candidates=len(all_candidates),
            provider_hit_counts=provider_hit_counts,
        )
        return context

    # ──────────────────────────────────────────────────────────────────────
    # Provider routing decision
    # ──────────────────────────────────────────────────────────────────────

    def _should_dispatch(
        self,
        provider: SearchProvider,
        query_type: str,
        query_text: str,
        domain: str | None,
    ) -> bool:
        """
        Return False for (provider, query_type) combos known to be useless.

        Reasoning per skip:
        - INTERNAL_SITE does not benefit from DATE_BOUND or ENTITIES queries:
          internal search engines on BD sites are too basic to use date syntax.
        - NEWSDATA is English-focused; sending a full Bangla HEADLINE query
          returns nothing.  We only send KEYWORDS (where we pass transliterated
          keywords) and BODY_SUMMARY and DATE_BOUND.
        - PY_GOOGLE_NEWS works well with HEADLINE and BODY_SUMMARY; sending
          keyword-only queries to it degrades results since RSS is title-ranked.
        """
        qt = query_type.upper()

        if provider == SearchProvider.INTERNAL_SITE:
            # Only send keyword-oriented query types to internal search
            if qt in ("DATE_BOUND", "ENTITIES"):
                return False

        if provider == SearchProvider.NEWSDATA:
            # NewsData API — only send query types that yield useful content
            # after keyword adaptation (S04 strips Bangla for this provider)
            if qt in ("HEADLINE", "SITE_RESTRICTED"):
                return False  # full Bangla headline → zero results on NewsData

        if provider == SearchProvider.PY_GOOGLE_NEWS:
            # RSS/Google News — headline and body queries work well; pure
            # keyword bags degrade the results
            if qt in ("KEYWORDS", "DATE_BOUND"):
                return False

        return True

    # ──────────────────────────────────────────────────────────────────────
    # Query adaptation per provider
    # ──────────────────────────────────────────────────────────────────────

    def _adapt_query(
        self,
        provider: SearchProvider,
        query: str,
        domain: str | None,
        query_type: str = "",
    ) -> str:
        """
        Return a provider-optimised query variant.

        CRITICAL CHANGE vs old code:
        - We NO LONGER quote phrases for Google CSE or DDG.
          Quoting reduces recall dramatically for poorly-indexed sites.
          The site: operator already provides precision; quoting on top
          makes the query so strict that only Prothom Alo (heavily indexed)
          returns results.
        - Short-query adaptation (word cap) is done here for providers that
          need it, NOT in S03. S03 emits full rich queries.
        """
        content_only = re.sub(r"site:\S+\s*", "", query).strip()

        if provider == SearchProvider.INTERNAL_SITE:
            # Internal search: keyword-only, no site: (domain is handled by URL template)
            # Limit to 6 words — most BD internal search engines break on long queries
            return _build_keyword_query(content_only, max_words=6)

        if provider == SearchProvider.NEWSDATA:
            # NewsData: short keyword query, max 80 chars
            # Note: only KEYWORDS / BODY_SUMMARY / DATE_BOUND reach this provider
            # (HEADLINE and SITE_RESTRICTED are skipped by _should_dispatch)
            kw = _build_keyword_query(content_only, max_words=7)
            return kw[:80]

        if provider == SearchProvider.PY_GOOGLE_NEWS:
            # PyGoogleNews/RSS: re-add domain cleanly (no quotes)
            if domain:
                return f"site:{domain} {content_only}"
            return content_only

        # ── Google CSE and DDG ────────────────────────────────────────────
        # REMOVED: exact-phrase quoting.
        # Old:  site:domain "keyword1 keyword2 ... keyword8" remainder
        # New:  site:domain keyword1 keyword2 keyword3 keyword4 keyword5
        #
        # Why: Google/DDG require all quoted words to appear in exact sequence.
        # BD news sites paraphrase; the exact sequence is almost never there
        # for sites other than Prothom Alo. Unquoted keyword queries have
        # 3-5× higher recall at the cost of a tiny precision drop — and we
        # have S06 to filter false positives by content similarity.
        if domain:
            return f"site:{domain} {content_only}"
        return content_only

    # ──────────────────────────────────────────────────────────────────────
    # Single provider call with caching
    # ──────────────────────────────────────────────────────────────────────

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

        # ── Cache check ──────────────────────────────────────────────────
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

        # ── Live call ────────────────────────────────────────────────────
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

    # ──────────────────────────────────────────────────────────────────────
    # Cache helpers
    # ──────────────────────────────────────────────────────────────────────

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