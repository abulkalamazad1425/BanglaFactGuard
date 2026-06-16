"""
app/pipelines/stages/s06_article_extractor.py
================================================
Stage 6: Article Content Extraction

## Responsibility

Extract structured article content (title, body, author, publication date)
from the raw HTML fetched in Stage 5, using a layered extraction chain:

## Extraction priority chain (per URL)

1. **Source-Specific CSS**  — title_selectors + body_selectors from source registry
                              (highest precision for known Bangla news sites)
2. **JSON-LD**              — Structured data embedded by the CMS
3. **Trafilatura**          — ML-based boilerplate removal (best general recall)
4. **Readability**          — Mozilla readability algorithm
5. **BeautifulSoup4**       — Pattern-based HTML parsing (generic fallback)
6. **OpenGraph meta**       — og:description as last-resort body

Title is always extracted via source-specific CSS first (not blocked by body state).
Date extraction uses date_selectors from the source registry.

## Article cache

Each extracted article is checked in Redis (bgf:article:{url_hash}).
On a hit the cached content is used (skips extraction).
On a miss the result is written back (non-blocking).

## Output

Populates context.extracted_articles as list[RankedArticleSchema] (rank_score=0.0).

## Criticality: NON-CRITICAL
Zero successful extractions → NOT_FOUND verdict in Stage 11. Pipeline continues.
"""

from __future__ import annotations

import asyncio
import json
import re
from datetime import date, datetime
from urllib.parse import urlparse

import trafilatura
from bs4 import BeautifulSoup
from readability import Document
import structlog

from app.core.config import get_settings
from app.core.constants import ExtractionMethod, PipelineStageID, SearchProvider
from app.features.verification.pipeline.context import PipelineContext
from app.features.articles.schemas import CandidateArticleSchema, RankedArticleSchema
from app.features.cache.cache_service import CacheService
from app.shared.utils.hashing import compute_url_hash
from app.shared.utils.text_cleaner import clean_extracted_text, clean_title

logger = structlog.get_logger(__name__)
_SETTINGS = get_settings()


class ArticleExtractorStage:
    """
    Stage 6: Extract article content from raw HTML using a layered chain.

    Dependencies:
        cache_service: For article content caching (Redis).
    """

    stage_id = PipelineStageID.S06_ARTICLE_EXTRACTOR

    def __init__(self, cache_service: CacheService) -> None:
        self._cache = cache_service
        self._min_body_length = _SETTINGS.search.min_body_length_chars

    async def execute(self, context: PipelineContext) -> PipelineContext:
        """
        Extract content from all successfully fetched URLs.

        Reads from context._raw_html_cache (dict[url → html_str]) set in S05.
        Writes to context.extracted_articles (list of RankedArticleSchema).
        """
        raw_html_cache: dict[str, str] = getattr(context, "_raw_html_cache", {})

        if not raw_html_cache:
            logger.debug(
                "s06_no_html_to_extract",
                claim_id=str(context.claim_id) if context.claim_id else "pending",
            )
            return context

        # Build url → candidate map for title-snippet fallbacks
        url_to_candidate: dict[str, CandidateArticleSchema] = {
            c.url: c for c in context.candidate_urls
        }

        # Resolve which source config applies (normalised domain comparison)
        normalized_source = getattr(context, "normalized_source", None)
        source_config = getattr(context, "source_config", None)

        loop = asyncio.get_event_loop()
        extraction_tasks = [
            loop.run_in_executor(
                None,
                self._extract_one,
                url,
                html,
                url_to_candidate,
                normalized_source,
                source_config,
            )
            for url, html in raw_html_cache.items()
        ]
        results = await asyncio.gather(*extraction_tasks, return_exceptions=True)

        extracted: list[RankedArticleSchema] = []
        for (url, _html), result in zip(raw_html_cache.items(), results):
            if isinstance(result, RankedArticleSchema):
                if result.has_body or result.title:
                    extracted.append(result)
                else:
                    context.failed_extraction_urls.append(result.url)
            elif isinstance(result, Exception):
                logger.warning("s06_extraction_exception", url=url[:80], error=str(result))
                context.failed_extraction_urls.append(url)

        context.extracted_articles = extracted
        logger.info(
            "s06_extraction_complete",
            attempted=len(raw_html_cache),
            succeeded=len(extracted),
            claim_id=str(context.claim_id) if context.claim_id else "pending",
        )
        return context

    # ------------------------------------------------------------------
    # Per-URL extraction (runs in thread pool — all code is synchronous)
    # ------------------------------------------------------------------

    def _extract_one(
        self,
        url: str,
        html: str,
        url_to_candidate: dict[str, CandidateArticleSchema],
        normalized_source: str | None,
        source_config: dict | None,
    ) -> RankedArticleSchema:
        """
        Extract content from a single HTML page using the layered chain.
        Runs in a thread pool (trafilatura / BS4 are synchronous / CPU-bound).
        """
        candidate = url_to_candidate.get(url)
        provider = candidate.search_provider if candidate else SearchProvider.GOOGLE_RSS

        # Resolve whether source_config applies to this URL
        url_domain = urlparse(url).netloc.replace("www.", "").split(":")[0].lower()
        src_domain = (normalized_source or "").replace("www.", "").split(":")[0].lower()
        use_config = bool(source_config) and bool(url_domain) and (url_domain == src_domain)
        config = source_config if use_config else None

        title: str | None = None
        body: str | None = None
        author: str | None = None
        pub_date: date | None = None
        method = ExtractionMethod.BEAUTIFULSOUP

        # Parse HTML once — reused by all extraction steps
        try:
            soup = BeautifulSoup(html, "lxml")
        except Exception:
            soup = BeautifulSoup(html, "html.parser")

        # ── Step 1: Source-Specific Title (always attempted first) ──────
        if config:
            for sel in config.get("title_selectors", []):
                try:
                    el = soup.select_one(sel)
                    if el:
                        candidate_title = el.get_text(strip=True)
                        if candidate_title and len(candidate_title) > 5:
                            title = candidate_title
                            break
                except Exception:
                    continue

        # ── Step 2: Source-Specific Date ────────────────────────────────
        if config and not pub_date:
            for sel in config.get("date_selectors", []):
                try:
                    el = soup.select_one(sel)
                    if el:
                        # Prefer datetime attribute, fall back to text content
                        date_text = el.get("datetime") or el.get_text(strip=True)
                        parsed = _parse_date_flexible(date_text)
                        if parsed:
                            pub_date = parsed
                            break
                except Exception:
                    continue

        # ── Step 3: Source-Specific Body ────────────────────────────────
        if config and (not body or len(body) < self._min_body_length):
            for sel in config.get("body_selectors", []):
                try:
                    els = soup.select(sel)
                    if els:
                        parts = []
                        for el in els:
                            # Collect all <p> text, or full text if no <p> children
                            p_tags = el.find_all("p")
                            if p_tags:
                                parts.append(
                                    "\n".join(p.get_text(strip=True) for p in p_tags if p.get_text(strip=True))
                                )
                            else:
                                txt = el.get_text(separator="\n", strip=True)
                                if txt:
                                    parts.append(txt)
                        combined = "\n".join(p for p in parts if p)
                        if combined and len(combined) > self._min_body_length:
                            body = combined
                            method = ExtractionMethod.SOURCE_SPECIFIC
                            break
                except Exception:
                    continue

        # ── Step 4: JSON-LD ─────────────────────────────────────────────
        if not body or len(body) < self._min_body_length:
            for script in soup.find_all("script", type="application/ld+json"):
                try:
                    data = json.loads(script.string or "")
                    items = data if isinstance(data, list) else [data]
                    for item in items:
                        if not isinstance(item, dict):
                            continue
                        if item.get("@type") not in ("NewsArticle", "Article", "ReportageNewsArticle"):
                            continue
                        ld_headline = item.get("headline")
                        if ld_headline and not title:
                            title = ld_headline
                        ld_body = item.get("articleBody", "")
                        if ld_body and len(ld_body) > self._min_body_length:
                            body = ld_body
                            # Author
                            auth_data = item.get("author")
                            if isinstance(auth_data, dict) and not author:
                                author = auth_data.get("name")
                            elif isinstance(auth_data, list) and auth_data and not author:
                                author = auth_data[0].get("name")
                            # Date
                            if not pub_date:
                                pub_date = _parse_date_flexible(item.get("datePublished", ""))
                            method = ExtractionMethod.JSON_LD
                            break
                except Exception:
                    continue
                if body and len(body) > self._min_body_length:
                    break

        # ── Step 5: Trafilatura ─────────────────────────────────────────
        if not body or len(body) < self._min_body_length:
            t_title, t_body, t_author, t_date = self._extract_trafilatura(url, html)
            if t_body and len(t_body) > self._min_body_length:
                title = title or t_title
                body = t_body
                author = author or t_author
                pub_date = pub_date or t_date
                method = ExtractionMethod.TRAFILATURA

        # ── Step 6: Readability ─────────────────────────────────────────
        if not body or len(body) < self._min_body_length:
            try:
                doc = Document(html)
                r_html = doc.summary()
                r_body = BeautifulSoup(r_html, "html.parser").get_text(separator="\n", strip=True)
                if r_body and len(r_body) > self._min_body_length:
                    title = title or doc.title()
                    body = r_body
                    method = ExtractionMethod.READABILITY
            except Exception:
                pass

        # ── Step 7: BeautifulSoup generic fallback ──────────────────────
        if not body or len(body) < self._min_body_length:
            bs_title, bs_body, bs_author, bs_date = self._extract_bs4(url, html)
            if bs_body and len(bs_body) > len(body or ""):
                title = title or bs_title
                body = bs_body
                author = author or bs_author
                pub_date = pub_date or bs_date
                method = ExtractionMethod.BEAUTIFULSOUP

        # ── Step 8: OpenGraph meta (absolute last resort for body) ───────
        if not title:
            og_title = soup.find("meta", property="og:title")
            if og_title and og_title.get("content"):
                title = og_title["content"]

        if not body or len(body) < self._min_body_length:
            og_desc = soup.find("meta", property="og:description")
            if og_desc and og_desc.get("content") and len(og_desc["content"]) > self._min_body_length:
                body = og_desc["content"]
                method = ExtractionMethod.OPENGRAPH

        if not pub_date:
            pub_time_meta = soup.find("meta", property="article:published_time")
            if pub_time_meta and pub_time_meta.get("content"):
                pub_date = _parse_date_flexible(pub_time_meta["content"])

        # ── Title fallback: use search-result snippet ────────────────────
        if candidate and candidate.title_snippet and (
            not title or title.strip().lower() in ("google news", "")
        ):
            title = candidate.title_snippet

        # ── Clean and return ─────────────────────────────────────────────
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
    ) -> tuple[str | None, str | None, str | None, date | None]:
        """Extract via trafilatura (best general-purpose news extractor)."""
        try:
            body = trafilatura.extract(
                html,
                url=url,
                include_comments=False,
                include_tables=False,
                no_fallback=False,
                favor_recall=True,
                deduplicate=True,
            )
            metadata = trafilatura.extract_metadata(html, url=url)
            title = author = None
            pub_date = None
            if metadata:
                title = metadata.title or None
                author = metadata.author or None
                if metadata.date:
                    pub_date = _parse_date_flexible(metadata.date)
            return title, body, author, pub_date
        except Exception as exc:
            logger.debug("s06_trafilatura_failed", url=url[:80], error=str(exc))
            return None, None, None, None

    def _extract_bs4(
        self, url: str, html: str
    ) -> tuple[str | None, str | None, str | None, date | None]:
        """Generic BeautifulSoup4 fallback extractor."""
        try:
            soup = BeautifulSoup(html, "lxml")
        except Exception:
            soup = BeautifulSoup(html, "html.parser")

        # Title
        title: str | None = None
        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"):
            title = og_title["content"]
        elif soup.find("h1"):
            title = soup.find("h1").get_text(strip=True)
        elif soup.title:
            title = soup.title.get_text(strip=True)

        # Author
        author: str | None = None
        author_meta = soup.find("meta", attrs={"name": "author"})
        if author_meta and author_meta.get("content"):
            author = author_meta["content"]

        # Date
        pub_date: date | None = None
        for attr in [
            {"property": "article:published_time"},
            {"name": "publish_date"},
            {"name": "dc.date"},
            {"itemprop": "datePublished"},
        ]:
            meta = soup.find("meta", attrs=attr)
            if meta and meta.get("content"):
                pub_date = _parse_date_flexible(meta["content"])
                if pub_date:
                    break

        # Remove boilerplate tags
        for tag in soup.find_all(["nav", "header", "footer", "aside", "script", "style", "noscript"]):
            tag.decompose()

        # Body — try semantic <article> first
        body: str | None = None
        article_el = soup.find("article")
        if article_el:
            body = article_el.get_text(separator="\n", strip=True)

        # Common content div patterns
        if not body or len(body) < self._min_body_length:
            content_patterns = [
                "article-body", "article_body", "post-content", "post_content",
                "entry-content", "entry_content", "content-body", "news-body",
                "story-body", "story_body", "article-content", "main-content",
                "news-content", "details-body", "reportBody", "dtl_content_block",
                "description", "detail-content", "details-text", "details-txt",
                "jw_article_body",
            ]
            for pattern in content_patterns:
                divs = soup.find_all(
                    "div",
                    class_=lambda c, p=pattern: c and p in c,
                )
                if divs:
                    candidate_text = "\n".join(
                        div.get_text(separator="\n", strip=True) for div in divs
                    )
                    if len(candidate_text) > len(body or ""):
                        body = candidate_text
                    break

        # Last resort: largest paragraph cluster
        if not body or len(body) < self._min_body_length:
            paragraphs = soup.find_all("p")
            body = "\n".join(
                p.get_text(strip=True)
                for p in paragraphs
                if len(p.get_text(strip=True)) > 30
            )

        return title, body or None, author, pub_date


# ------------------------------------------------------------------
# Date parsing utility
# ------------------------------------------------------------------

_DATE_PATTERNS = [
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M:%S.%f%z",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d",
    "%d/%m/%Y",
    "%B %d, %Y",
    "%d %B %Y",
]


def _parse_date_flexible(raw: str | None) -> date | None:
    """
    Try to parse a date string into a date object using multiple formats.
    Handles ISO-8601 with timezone, slash-separated, and natural language dates.
    Returns None if all formats fail.
    """
    if not raw:
        return None
    raw = raw.strip()
    # Normalise timezone: 'Z' → '+00:00'
    raw_norm = raw.replace("Z", "+00:00")
    # Try fromisoformat first (handles most ISO-8601 variants)
    try:
        return datetime.fromisoformat(raw_norm[:19]).date()
    except (ValueError, TypeError):
        pass
    # Try explicit patterns
    for fmt in _DATE_PATTERNS:
        try:
            return datetime.strptime(raw[:len(fmt) + 5], fmt).date()
        except (ValueError, TypeError):
            continue
    return None
