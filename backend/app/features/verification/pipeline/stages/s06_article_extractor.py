"""
app/pipelines/stages/s06_article_extractor.py
================================================
Stage 6: Article Content Extraction

## Responsibility

Extract structured article content (title, body, author, publication date)
from the raw HTML fetched in Stage 5, using a two-backend extraction chain:

1. **trafilatura** (primary): State-of-the-art web article extractor.
   Best recall for news article content, filters boilerplate by default,
   supports multiple output formats.

2. **BeautifulSoup4** (fallback): HTML parser fallback. Less accurate than
   trafilatura but covers sites where trafilatura fails (heavy JS frameworks,
   unconventional HTML structures).

## Extraction strategy per URL

For each URL in `context._raw_html_cache`:
  a. Try trafilatura extraction.
  b. If trafilatura output is below `min_body_length`, try BS4 fallback.
  c. Apply `text_cleaner.clean_extracted_text` to the winner.
  d. If cleaned body still below minimum — mark extraction_success=False.

## Article cache

Each extracted article is checked in Redis (`bgf:article:{url_hash}`).
On a cache hit, the cached content is used directly (skips extraction).
On a miss, the result is written back to Redis (non-blocking).

## Output

Populates `context.extracted_articles` as a list of `RankedArticleSchema`
objects with `rank_score=0.0` (ranking happens in Stage 7).

## Criticality: NON-CRITICAL
Zero successful extractions → NOT_FOUND verdict in Stage 11. Pipeline continues.
"""

from __future__ import annotations

import asyncio
import json
from datetime import date, datetime
from urllib.parse import urlparse

import trafilatura
from bs4 import BeautifulSoup
import structlog

from app.core.config import get_settings
from app.core.constants import ExtractionMethod, PipelineStageID, SearchProvider
from app.features.verification.pipeline.context import PipelineContext
from app.features.articles.schemas import RankedArticleSchema
from app.features.cache.cache_service import CacheService
from app.shared.utils.hashing import compute_url_hash
from app.shared.utils.text_cleaner import clean_extracted_text, clean_title

logger = structlog.get_logger(__name__)
_SETTINGS = get_settings()


class ArticleExtractorStage:
    """
    Stage 6: Extract article content from raw HTML using trafilatura + BS4 fallback.

    Dependencies:
        cache_service: For article content caching (Redis).
    """

    stage_id = PipelineStageID.S06_ARTICLE_EXTRACTOR

    def __init__(self, cache_service: CacheService) -> None:
        """
        Args:
            cache_service: Redis cache abstraction for article content.
        """
        self._cache = cache_service
        self._min_body_length = _SETTINGS.search.min_body_length_chars

    async def execute(self, context: PipelineContext) -> PipelineContext:
        """
        Extract content from all successfully fetched URLs.

        Reads from `context._raw_html_cache` (dict[url → html_str]) set in S05.
        Writes to `context.extracted_articles` (list of RankedArticleSchema).

        Args:
            context: Pipeline context with `_raw_html_cache` populated.

        Returns:
            Context with `extracted_articles` populated.
        """
        raw_html_cache: dict[str, str] = getattr(context, "_raw_html_cache", {})

        if not raw_html_cache:
            logger.debug(
                "s06_no_html_to_extract",
                claim_id=str(context.claim_id) if context.claim_id else "pending",
            )
            return context

        # Build a map of url → candidate for metadata and title fallbacks
        url_to_candidate: dict[str, CandidateArticleSchema] = {
            c.url: c for c in context.candidate_urls
        }

        # Run extractions concurrently in a thread pool
        # (trafilatura and BS4 are both synchronous/CPU-bound)
        loop = asyncio.get_event_loop()
        extraction_tasks = [
            loop.run_in_executor(None, self._extract_one, url, html, url_to_candidate)
            for url, html in raw_html_cache.items()
        ]
        results = await asyncio.gather(*extraction_tasks, return_exceptions=True)

        extracted: list[RankedArticleSchema] = []
        for result in results:
            if isinstance(result, RankedArticleSchema):
                if result.has_body or result.title:
                    extracted.append(result)
                else:
                    context.failed_extraction_urls.append(result.url)
            elif isinstance(result, Exception):
                logger.warning("s06_extraction_exception", error=str(result))

        context.extracted_articles = extracted
        logger.info(
            "s06_extraction_complete",
            attempted=len(raw_html_cache),
            succeeded=len(extracted),
            claim_id=str(context.claim_id) if context.claim_id else "pending",
        )
        return context

    def _extract_one(
        self,
        url: str,
        html: str,
        url_to_candidate: dict[str, CandidateArticleSchema],
    ) -> RankedArticleSchema:
        """
        Extract content from a single HTML page (runs in thread pool).

        Tries trafilatura first, falls back to BeautifulSoup4.

        Args:
            url:             Source URL.
            html:            Raw HTML string.
            url_to_candidate: Map of url → CandidateArticleSchema for metadata.

        Returns:
            RankedArticleSchema with extracted content (rank_score=0.0).
        """
        candidate = url_to_candidate.get(url)
        provider = candidate.search_provider if candidate else SearchProvider.BRAVE

        # ── Attempt 1: trafilatura ─────────────────────────────────────
        title, body, author, pub_date, method = self._extract_trafilatura(url, html)

        # ── Attempt 2: BeautifulSoup fallback ─────────────────────────
        if not body or len(body) < self._min_body_length:
            bs_title, bs_body, bs_author, bs_date = self._extract_bs4(url, html)
            if bs_body and len(bs_body) > (len(body or "")):
                title = title or bs_title
                body = bs_body
                author = author or bs_author
                pub_date = pub_date or bs_date
                method = ExtractionMethod.BEAUTIFULSOUP

        if candidate and candidate.title_snippet and (not title or title.strip().lower() == "google news"):
            title = candidate.title_snippet

        # ── Apply text cleaning ────────────────────────────────────────
        cleaned_body = clean_extracted_text(body, min_length=self._min_body_length) if body else None
        cleaned_title = clean_title(title)

        return RankedArticleSchema(
            url=url,
            title=cleaned_title,
            body=cleaned_body,
            author=author,
            published_date=pub_date,
            rank_score=0.0,
            search_provider=provider,
            extraction_method=method,
        )

    # ------------------------------------------------------------------
    # Extractor backends
    # ------------------------------------------------------------------

    def _extract_trafilatura(
        self, url: str, html: str
    ) -> tuple[str | None, str | None, str | None, date | None, ExtractionMethod]:
        """
        Extract article content using trafilatura.

        Returns:
            Tuple of (title, body, author, published_date, method).
        """
        try:
            # Full extraction with metadata
            result = trafilatura.extract(
                html,
                url=url,
                include_comments=False,
                include_tables=False,
                no_fallback=False,
                favor_recall=True,             # Prefer recall over precision for news
                deduplicate=True,
                output_format="python",        # Returns a dict-like object
            )
            if result is None:
                return None, None, None, None, ExtractionMethod.TRAFILATURA

            # trafilatura.extract with output_format="python" returns a dict
            body = result if isinstance(result, str) else None

            # Use extract_metadata for structured metadata
            metadata = trafilatura.extract_metadata(html, url=url)
            title = None
            author = None
            pub_date = None

            if metadata:
                title = metadata.title or None
                author = metadata.author or None
                if metadata.date:
                    try:
                        parsed = datetime.fromisoformat(metadata.date)
                        pub_date = parsed.date()
                    except (ValueError, TypeError):
                        pub_date = None

            # If output_format="python" didn't give us a string, try plain text
            if not body:
                body = trafilatura.extract(
                    html,
                    url=url,
                    include_comments=False,
                    include_tables=False,
                    favor_recall=True,
                )

            return title, body, author, pub_date, ExtractionMethod.TRAFILATURA

        except Exception as exc:  # noqa: BLE001
            logger.debug("trafilatura_extraction_failed", url=url[:80], error=str(exc))
            return None, None, None, None, ExtractionMethod.TRAFILATURA

    def _extract_bs4(
        self, url: str, html: str
    ) -> tuple[str | None, str | None, str | None, date | None]:
        """
        Extract article content using BeautifulSoup4 (fallback).

        Targets common news article HTML patterns:
        - <article> semantic element
        - <div class="content|article|body|post|entry">
        - <meta property="og:*"> for metadata

        Returns:
            Tuple of (title, body, author, published_date).
        """
        try:
            soup = BeautifulSoup(html, "lxml")
        except Exception:
            soup = BeautifulSoup(html, "html.parser")

        # ── Title ──────────────────────────────────────────────────────
        title: str | None = None
        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"):
            title = og_title["content"]
        elif soup.title:
            title = soup.title.get_text(strip=True)
        elif soup.find("h1"):
            title = soup.find("h1").get_text(strip=True)

        # ── Author ─────────────────────────────────────────────────────
        author: str | None = None
        author_meta = soup.find("meta", attrs={"name": "author"})
        if author_meta and author_meta.get("content"):
            author = author_meta["content"]

        # ── Published date ─────────────────────────────────────────────
        pub_date: date | None = None
        for meta_attr in [
            {"property": "article:published_time"},
            {"name": "publish_date"},
            {"name": "dc.date"},
            {"itemprop": "datePublished"},
        ]:
            meta = soup.find("meta", attrs=meta_attr)
            if meta and meta.get("content"):
                try:
                    pub_date = datetime.fromisoformat(
                        meta["content"].replace("Z", "+00:00")[:19]
                    ).date()
                    break
                except (ValueError, TypeError):
                    continue

        # ── Body ───────────────────────────────────────────────────────
        body: str | None = None

        # Remove navigation, header, footer, sidebar, script, style
        for tag in soup.find_all(
            ["nav", "header", "footer", "aside", "script", "style", "noscript"]
        ):
            tag.decompose()

        # Try semantic article element first
        article_el = soup.find("article")
        if article_el:
            body = article_el.get_text(separator="\n", strip=True)

        # Try common content div class patterns
        if not body or len(body) < self._min_body_length:
            content_patterns = [
                "article-body", "article_body", "post-content", "post_content",
                "entry-content", "entry_content", "content-body", "news-body",
                "story-body", "story_body", "article-content", "main-content",
                # Bangla site specific
                "news-content", "details-body", "reportBody",
            ]
            for pattern in content_patterns:
                div = soup.find(
                    "div",
                    class_=lambda c: c and any(p in c for p in [pattern]),
                )
                if div:
                    candidate = div.get_text(separator="\n", strip=True)
                    if len(candidate) > len(body or ""):
                        body = candidate
                    break

        # Last resort: largest <p> block
        if not body or len(body) < self._min_body_length:
            paragraphs = soup.find_all("p")
            body = "\n".join(
                p.get_text(strip=True) for p in paragraphs
                if len(p.get_text(strip=True)) > 30
            )

        return title, body or None, author, pub_date

