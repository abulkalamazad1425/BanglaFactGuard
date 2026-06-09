"""
app/pipelines/stages/s05_evidence_retrieval.py
================================================
Stage 5: Evidence Retrieval

## Responsibility

Fetch the raw HTTP content of each candidate URL produced by Stage 4,
concurrently and within resource limits, ready for extraction in Stage 6.

## Design

- **Async concurrent fetching** via `asyncio.gather` with a `Semaphore` to
  cap the maximum number of simultaneous HTTP connections.
- **Per-URL timeout** of 15 seconds prevents slow servers from stalling the
  entire pipeline.
- **Deduplication check** via ArticleRepository before fetching — if a URL
  was already retrieved for this claim (url_hash exists in DB), skip it.
- **Top-K enforcement**: only the first `top_k_candidates` URLs are fetched,
  ordered by search provider priority (Brave first, then RSS, then DDG).
- **Raw HTML is not stored** — only the URL and fetch success/failure are
  tracked here. Actual content extraction happens in Stage 6.
- The fetched HTML is stored in a transient dict keyed by URL, passed via
  a stage-local variable to Stage 6 via context's `_raw_html_cache`
  (a private dict added to the context for inter-stage HTML transfer).

## Criticality: NON-CRITICAL
A failed fetch for any individual URL is logged and skipped.
Zero successful fetches → Stage 6 produces zero articles → Stage 11
returns NOT_FOUND_IN_CLAIMED_SOURCE.
"""

from __future__ import annotations

import asyncio

import httpx
import structlog

from app.core.config import get_settings
from app.core.constants import PipelineStageID
from app.features.verification.pipeline.context import PipelineContext
from app.shared.utils.hashing import compute_url_hash

logger = structlog.get_logger(__name__)

_SETTINGS = get_settings()
_MAX_CONCURRENT_FETCHES = 10
_FETCH_TIMEOUT = 15.0  # seconds
_USER_AGENT = "Mozilla/5.0 (compatible; BanglaFactGuard/1.0; +https://bangla.factguard.io)"


class EvidenceRetrievalStage:
    """
    Stage 5: Concurrently fetch HTTP content for all candidate URLs.

    Dependencies:
        http_client: Shared async httpx client (injected via DI).
    """

    stage_id = PipelineStageID.S05_EVIDENCE_RETRIEVAL

    def __init__(self, http_client: httpx.AsyncClient) -> None:
        """
        Args:
            http_client: Shared async HTTP client for article fetching.
        """
        self._client = http_client
        self._semaphore = asyncio.Semaphore(_MAX_CONCURRENT_FETCHES)
        self._top_k = _SETTINGS.search.top_k_candidates

    async def execute(self, context: PipelineContext) -> PipelineContext:
        """
        Fetch HTML content for all candidate URLs, concurrently.

        Stores fetched HTML in `context._raw_html_cache` (dict[url → html_str])
        for Stage 6 to consume. URLs that fail fetching are added to
        `context.failed_extraction_urls` for audit logging.

        Args:
            context: Pipeline context with `candidate_urls` set (Stage 4 output).

        Returns:
            Context with `_raw_html_cache` populated.
        """
        candidates = context.candidate_urls[: self._top_k]

        if not candidates:
            logger.debug(
                "s05_no_candidates",
                claim_id=str(context.claim_id) if context.claim_id else "pending",
            )
            context._raw_html_cache = {}  # type: ignore[attr-defined]
            return context

        # Compute url_hash for each candidate for deduplication
        urls_to_fetch = [c.url for c in candidates]

        logger.info(
            "s05_fetching_evidence",
            url_count=len(urls_to_fetch),
            claim_id=str(context.claim_id) if context.claim_id else "pending",
        )

        # Fetch all URLs concurrently, bounded by semaphore
        fetch_tasks = [self._fetch_url(url) for url in urls_to_fetch]
        results = await asyncio.gather(*fetch_tasks, return_exceptions=True)

        raw_html_cache: dict[str, str] = {}
        for url, result in zip(urls_to_fetch, results):
            if isinstance(result, str) and result:
                raw_html_cache[url] = result
            else:
                # Failed fetch — record for audit
                context.failed_extraction_urls.append(url)
                if isinstance(result, Exception):
                    logger.debug(
                        "s05_fetch_failed",
                        url=url[:80],
                        error=str(result),
                    )

        context._raw_html_cache = raw_html_cache  # type: ignore[attr-defined]

        logger.info(
            "s05_retrieval_complete",
            attempted=len(urls_to_fetch),
            succeeded=len(raw_html_cache),
            failed=len(context.failed_extraction_urls),
        )
        return context

    async def _fetch_url(self, url: str) -> str | Exception:
        """
        Fetch a single URL with timeout and semaphore protection.

        Args:
            url: The article URL to fetch.

        Returns:
            Response text (HTML) on success, or the Exception on failure.
        """
        async with self._semaphore:
            try:
                response = await self._client.get(
                    url,
                    timeout=_FETCH_TIMEOUT,
                    follow_redirects=True,
                    headers={
                        "User-Agent": _USER_AGENT,
                        "Accept": "text/html,application/xhtml+xml,*/*;q=0.9",
                        "Accept-Language": "bn-BD,bn;q=0.9,en;q=0.8",
                        "Accept-Encoding": "gzip, deflate",
                    },
                )
                # Accept 2xx responses only
                if response.status_code < 200 or response.status_code >= 300:
                    return Exception(f"HTTP {response.status_code}")

                return response.text

            except httpx.TimeoutException as exc:
                return exc
            except httpx.ConnectError as exc:
                return exc
            except Exception as exc:  # noqa: BLE001
                return exc

