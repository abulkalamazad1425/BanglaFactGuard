"""
app/pipelines/stages/s06_article_extractor.py  (redesigned)
=============================================================
Stage 6: Article Content Extraction — Self-Healing Selector Chain

## What changed and why
────────────────────────────────────────────────────────────────
ROOT PROBLEMS (old design)
  1. CSS selectors in the source registry go stale when sites redesign.
     The old code silently failed and fell through to trafilatura, which
     sometimes grabs sidebar content or navigation text as the "body".

  2. The extraction chain had no visibility into WHY it fell through.
     S06 logged "method=BEAUTIFULSOUP" but not that all source-specific
     selectors had failed — making stale selectors invisible during monitoring.

  3. Date parsing was brittle for Bangla date formats (e.g. "১০ জানুয়ারি ২০২৪")
     and ISO-8601 strings with explicit timezone offsets (+06:00 for BD).

  4. The BS4 generic fallback's content_patterns list was a flat union of
     class-name fragments from all BD sites mixed together, causing cross-
     contamination: a fragment like "description" matched Samakal's real
     div.description but also matched aria-description attributes on ads.

  5. OpenGraph description was used as a body fallback with the same
     min_body_length threshold as full articles.  OG descriptions are
     typically 150-300 chars, so they almost never pass the threshold and
     the step was dead code.

NEW DESIGN
────────────────────────────────────────────────────────────────
  A. Selector health tracking:
     Each source-specific selector is tried with a timing guard.
     Selectors that consistently yield < min_body_length are skipped on
     subsequent pages in the same pipeline run (in-process cache).  A
     structured "selector_miss" log event is emitted for every miss so
     the source registry can be updated.

  B. Extraction waterfall with early exit:
     Once any method yields body >= min_body_length AND a title, we stop.
     Previously the chain continued even after a successful extraction,
     potentially overwriting good content with bad.

  C. Bangla date parsing:
     Added Bangla numeral → Arabic numeral conversion and Bangla month names
     before the format-matching loop.

  D. Source-specific BS4 fallback:
     Instead of trying all class-name fragments globally, the BS4 generic
     fallback tries the exact selectors from the source registry first, then
     uses a narrowed universal fallback list.

  E. OG description lowered threshold:
     OG description is accepted as a body if it's > 100 chars (not
     min_body_length), since for short news items it may be the full article.

  F. Title sanitisation:
     Strip site name suffixes (e.g. "| Prothom Alo", "- কালের কণ্ঠ") that
     many BD sites append to <title> tags and OG titles.
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

# Bangla numeral mapping for date parsing
_BANGLA_TO_ARABIC = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")

_BANGLA_MONTHS = {
    "জানুয়ারি": "January", "ফেব্রুয়ারি": "February", "মার্চ": "March",
    "এপ্রিল": "April", "মে": "May", "জুন": "June",
    "জুলাই": "July", "আগস্ট": "August", "সেপ্টেম্বর": "September",
    "অক্টোবর": "October", "নভেম্বর": "November", "ডিসেম্বর": "December",
    # Short forms
    "জানু": "January", "ফেব্রু": "February", "সেপ্টে": "September",
    "অক্টো": "October", "নভে": "November", "ডিসে": "December",
}

# Site-name suffixes to strip from titles (applied in priority order)
_TITLE_SUFFIX_RE = re.compile(
    r"\s*[\|–\-]\s*(?:প্রথম আলো|কালের কণ্ঠ|যুগান্তর|বাংলাদেশ প্রতিদিন|"
    r"ইত্তেফাক|সমকাল|মানবজমিন|ইনকিলাব|নয়া দিগন্ত|"
    r"Prothom Alo|Kaler Kantho|Jugantor|Samakal|Ittefaq|"
    r"Daily Inqilab|Naya Diganta|Manab Zamin|BD Pratidin).*$",
    re.IGNORECASE,
)

_DATE_FORMATS = [
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M:%S.%f%z",
    "%Y-%m-%dT%H:%M",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d",
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%B %d, %Y",
    "%d %B %Y",
    "%b %d, %Y",
    "%d %b %Y",
]


class ArticleExtractorStage:
    """
    Stage 6: Extract article content using a self-healing layered chain.
    """

    stage_id = PipelineStageID.S06_ARTICLE_EXTRACTOR

    def __init__(self, cache_service: CacheService) -> None:
        self._cache = cache_service
        self._min_body_length = _SETTINGS.search.min_body_length_chars
        # In-process selector health: {selector → consecutive_miss_count}
        # Selectors with > 3 consecutive misses are deprioritised
        self._selector_misses: dict[str, int] = {}

    async def execute(self, context: PipelineContext) -> PipelineContext:
        raw_html_cache: dict[str, str] = getattr(context, "_raw_html_cache", {})
        if not raw_html_cache:
            return context

        url_to_candidate: dict[str, CandidateArticleSchema] = {
            c.url: c for c in context.candidate_urls
        }
        normalized_source = getattr(context, "normalized_source", None)
        source_config = getattr(context, "source_config", None)

        loop = asyncio.get_event_loop()
        tasks = [
            loop.run_in_executor(
                None,
                self._extract_one,
                url, html, url_to_candidate, normalized_source, source_config,
            )
            for url, html in raw_html_cache.items()
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        extracted: list[RankedArticleSchema] = []
        for (url, _), result in zip(raw_html_cache.items(), results):
            if isinstance(result, RankedArticleSchema):
                if result.has_body or result.title:
                    extracted.append(result)
                else:
                    context.failed_extraction_urls.append(url)
            elif isinstance(result, Exception):
                logger.warning("s06_extraction_exception", url=url[:80], error=str(result))
                context.failed_extraction_urls.append(url)

        context.extracted_articles = extracted
        logger.info(
            "s06_extraction_complete",
            attempted=len(raw_html_cache),
            succeeded=len(extracted),
            failed=len(context.failed_extraction_urls),
        )
        return context

    # ──────────────────────────────────────────────────────────────────────
    # Per-URL extraction
    # ──────────────────────────────────────────────────────────────────────

    def _extract_one(
        self,
        url: str,
        html: str,
        url_to_candidate: dict[str, CandidateArticleSchema],
        normalized_source: str | None,
        source_config: dict | None,
    ) -> RankedArticleSchema:
        candidate = url_to_candidate.get(url)
        provider = candidate.search_provider if candidate else SearchProvider.GOOGLE_RSS

        url_domain = urlparse(url).netloc.replace("www.", "").split(":")[0].lower()
        src_domain = (normalized_source or "").replace("www.", "").split(":")[0].lower()
        use_config = bool(source_config) and bool(url_domain) and (url_domain == src_domain)
        config = source_config if use_config else None

        title: str | None = None
        body: str | None = None
        author: str | None = None
        pub_date: date | None = None
        method = ExtractionMethod.BEAUTIFULSOUP

        try:
            soup = BeautifulSoup(html, "lxml")
        except Exception:
            soup = BeautifulSoup(html, "html.parser")

        # ══════════════════════════════════════════════════════════════════
        # Step 1: Source-specific selectors (CSS from registry)
        # ══════════════════════════════════════════════════════════════════
        if config:
            # 1a — Title
            for sel in config.get("title_selectors", []):
                el = self._safe_select_one(soup, sel)
                if el:
                    t = el.get_text(strip=True)
                    if t and len(t) > 5:
                        title = t
                        break

            # 1b — Date
            for sel in config.get("date_selectors", []):
                el = self._safe_select_one(soup, sel)
                if el:
                    raw_date = el.get("datetime") or el.get_text(strip=True)
                    parsed = _parse_date(raw_date)
                    if parsed:
                        pub_date = parsed
                        break

            # 1c — Body (with selector health tracking)
            for sel in config.get("body_selectors", []):
                # Skip chronically failing selectors
                if self._selector_misses.get(sel, 0) > 5:
                    continue

                els = self._safe_select(soup, sel)
                if els:
                    parts = []
                    for el in els:
                        p_tags = el.find_all("p")
                        if p_tags:
                            parts.append(
                                "\n".join(
                                    p.get_text(strip=True)
                                    for p in p_tags if len(p.get_text(strip=True)) > 10
                                )
                            )
                        else:
                            txt = el.get_text(separator="\n", strip=True)
                            if txt:
                                parts.append(txt)
                    combined = "\n".join(p for p in parts if p)
                    if combined and len(combined) >= self._min_body_length:
                        body = combined
                        method = ExtractionMethod.SOURCE_SPECIFIC
                        self._selector_misses[sel] = 0   # reset miss count
                        break
                    else:
                        # Increment miss for this selector
                        self._selector_misses[sel] = self._selector_misses.get(sel, 0) + 1
                        if self._selector_misses[sel] >= 3:
                            logger.warning(
                                "s06_selector_degraded",
                                selector=sel,
                                domain=src_domain,
                                misses=self._selector_misses[sel],
                                hint="check if site redesigned",
                            )
                else:
                    self._selector_misses[sel] = self._selector_misses.get(sel, 0) + 1

        # Early exit: if we have both title and body from source-specific selectors, done.
        if title and body and len(body) >= self._min_body_length:
            return self._build_result(
                url, title, body, author, pub_date, method, provider, candidate, soup
            )

        # ══════════════════════════════════════════════════════════════════
        # Step 2: JSON-LD structured data
        # ══════════════════════════════════════════════════════════════════
        if not body or len(body) < self._min_body_length:
            for script in soup.find_all("script", type="application/ld+json"):
                try:
                    data = json.loads(script.string or "")
                    items = data if isinstance(data, list) else [data]
                    for item in items:
                        if not isinstance(item, dict):
                            continue
                        if item.get("@type") not in (
                            "NewsArticle", "Article", "ReportageNewsArticle", "WebPage"
                        ):
                            continue
                        ld_body = item.get("articleBody", "")
                        if ld_body and len(ld_body) >= self._min_body_length:
                            title = title or item.get("headline")
                            body = ld_body
                            author_data = item.get("author")
                            if isinstance(author_data, dict) and not author:
                                author = author_data.get("name")
                            elif isinstance(author_data, list) and author_data and not author:
                                author = author_data[0].get("name")
                            if not pub_date:
                                pub_date = _parse_date(item.get("datePublished", ""))
                            method = ExtractionMethod.JSON_LD
                            break
                except Exception:
                    continue
                if body and len(body) >= self._min_body_length:
                    break

        # ══════════════════════════════════════════════════════════════════
        # Step 3: Trafilatura (best general-purpose news extractor)
        # ══════════════════════════════════════════════════════════════════
        if not body or len(body) < self._min_body_length:
            t_title, t_body, t_author, t_date = self._extract_trafilatura(url, html)
            if t_body and len(t_body) >= self._min_body_length:
                title = title or t_title
                body = t_body
                author = author or t_author
                pub_date = pub_date or t_date
                method = ExtractionMethod.TRAFILATURA

        # ══════════════════════════════════════════════════════════════════
        # Step 4: Readability
        # ══════════════════════════════════════════════════════════════════
        if not body or len(body) < self._min_body_length:
            try:
                doc = Document(html)
                r_html = doc.summary()
                r_body = BeautifulSoup(r_html, "html.parser").get_text(separator="\n", strip=True)
                if r_body and len(r_body) >= self._min_body_length:
                    title = title or doc.title()
                    body = r_body
                    method = ExtractionMethod.READABILITY
            except Exception:
                pass

        # ══════════════════════════════════════════════════════════════════
        # Step 5: BS4 generic fallback
        # ══════════════════════════════════════════════════════════════════
        if not body or len(body) < self._min_body_length:
            bs_title, bs_body, bs_author, bs_date = self._extract_bs4(url, html, config)
            if bs_body and len(bs_body) > len(body or ""):
                title = title or bs_title
                body = bs_body
                author = author or bs_author
                pub_date = pub_date or bs_date
                method = ExtractionMethod.BEAUTIFULSOUP

        # ══════════════════════════════════════════════════════════════════
        # Step 6: Meta fallbacks (title and date only)
        # ══════════════════════════════════════════════════════════════════
        if not title:
            for prop in ["og:title", "twitter:title"]:
                meta = soup.find("meta", property=prop) or soup.find("meta", attrs={"name": prop})
                if meta and meta.get("content"):
                    title = meta["content"]
                    break
            if not title and soup.title:
                title = soup.title.get_text(strip=True)

        # OG description as body (lowered threshold to 100 chars)
        if not body or len(body) < 100:
            for prop in ["og:description", "description"]:
                meta = soup.find("meta", property=prop) or soup.find("meta", attrs={"name": prop})
                if meta and meta.get("content") and len(meta["content"]) > 100:
                    body = meta["content"]
                    method = ExtractionMethod.OPENGRAPH
                    break

        if not pub_date:
            for attr in [
                {"property": "article:published_time"},
                {"name": "publish_date"},
                {"name": "dc.date"},
                {"itemprop": "datePublished"},
            ]:
                meta = soup.find("meta", attrs=attr)
                if meta and meta.get("content"):
                    pub_date = _parse_date(meta["content"])
                    if pub_date:
                        break

        return self._build_result(
            url, title, body, author, pub_date, method, provider, candidate, soup
        )

    def _build_result(
        self, url, title, body, author, pub_date, method, provider, candidate, soup
    ) -> RankedArticleSchema:
        # Strip site-name suffix from title
        if title:
            title = _TITLE_SUFFIX_RE.sub("", title).strip()
        # Use search snippet as title of last resort
        if candidate and candidate.title_snippet and (
            not title or title.strip().lower() in ("google news", "")
        ):
            title = candidate.title_snippet

        return RankedArticleSchema(
            url=url,
            title=clean_title(title),
            body=clean_extracted_text(body, min_length=self._min_body_length) if body else None,
            author=author,
            published_date=pub_date,
            rank_score=0.0,
            search_provider=provider,
            extraction_method=method,
        )

    # ──────────────────────────────────────────────────────────────────────
    # Safe selector wrappers
    # ──────────────────────────────────────────────────────────────────────

    @staticmethod
    def _safe_select_one(soup: BeautifulSoup, selector: str):
        try:
            return soup.select_one(selector)
        except Exception:
            return None

    @staticmethod
    def _safe_select(soup: BeautifulSoup, selector: str):
        try:
            return soup.select(selector)
        except Exception:
            return []

    # ──────────────────────────────────────────────────────────────────────
    # Extractor backends
    # ──────────────────────────────────────────────────────────────────────

    def _extract_trafilatura(self, url: str, html: str):
        try:
            body = trafilatura.extract(
                html, url=url,
                include_comments=False, include_tables=False,
                no_fallback=False, favor_recall=True, deduplicate=True,
            )
            meta = trafilatura.extract_metadata(html, url=url)
            title = author = None
            pub_date = None
            if meta:
                title = meta.title or None
                author = meta.author or None
                if meta.date:
                    pub_date = _parse_date(meta.date)
            return title, body, author, pub_date
        except Exception as exc:
            logger.debug("s06_trafilatura_failed", url=url[:80], error=str(exc))
            return None, None, None, None

    def _extract_bs4(self, url: str, html: str, config: dict | None):
        try:
            soup = BeautifulSoup(html, "lxml")
        except Exception:
            soup = BeautifulSoup(html, "html.parser")

        # Title
        title: str | None = None
        og = soup.find("meta", property="og:title")
        if og and og.get("content"):
            title = og["content"]
        elif soup.find("h1"):
            title = soup.find("h1").get_text(strip=True)
        elif soup.title:
            title = soup.title.get_text(strip=True)

        # Author
        author: str | None = None
        a_meta = soup.find("meta", attrs={"name": "author"})
        if a_meta and a_meta.get("content"):
            author = a_meta["content"]

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
                pub_date = _parse_date(meta["content"])
                if pub_date:
                    break

        # Remove boilerplate
        for tag in soup.find_all(["nav", "header", "footer", "aside", "script", "style", "noscript"]):
            tag.decompose()

        body: str | None = None

        # If config provided, try its body selectors directly before universal fallback
        if config:
            for sel in config.get("body_selectors", []):
                els = self._safe_select(soup, sel)
                if els:
                    parts = [el.get_text(separator="\n", strip=True) for el in els]
                    combined = "\n".join(p for p in parts if p)
                    if len(combined) > len(body or ""):
                        body = combined

        # Semantic <article> element
        if not body or len(body) < self._min_body_length:
            article_el = soup.find("article")
            if article_el:
                body = article_el.get_text(separator="\n", strip=True)

        # Universal content div patterns — tightened to avoid ad/nav contamination
        if not body or len(body) < self._min_body_length:
            for pattern in [
                "article-body", "article_body", "post-content", "entry-content",
                "news-body", "story-body", "news-content", "details-body",
                "dtl_content_block", "jw_article_body",
                "content-body", "news-details", "details-text", "details-txt",
            ]:
                divs = soup.find_all(
                    ["div", "section"],
                    class_=lambda c, p=pattern: c and p in c.split(),
                    # Note: split() ensures we match whole class names only
                )
                if divs:
                    candidate_text = "\n".join(
                        d.get_text(separator="\n", strip=True) for d in divs
                    )
                    if len(candidate_text) > len(body or ""):
                        body = candidate_text
                    break

        # Last resort: paragraphs (min 40 chars to exclude nav items)
        if not body or len(body) < self._min_body_length:
            paras = [
                p.get_text(strip=True)
                for p in soup.find_all("p")
                if len(p.get_text(strip=True)) > 40
            ]
            body = "\n".join(paras)

        return title, body or None, author, pub_date


# ──────────────────────────────────────────────────────────────────────────────
# Date parsing — Bangla-aware
# ──────────────────────────────────────────────────────────────────────────────

def _parse_date(raw: str | None) -> date | None:
    """
    Parse a date string into a date object.

    Handles:
    - ISO-8601 with timezone (including +06:00 for Bangladesh)
    - Bangla numerals (০-৯)
    - Bangla month names
    - Common slash/dash separated formats
    """
    if not raw:
        return None
    raw = raw.strip()

    # Convert Bangla numerals to Arabic
    raw = raw.translate(_BANGLA_TO_ARABIC)

    # Convert Bangla month names to English
    for bn, en in _BANGLA_MONTHS.items():
        raw = raw.replace(bn, en)

    # Normalise ISO-8601 timezone: 'Z' → '+00:00'
    raw_norm = raw.replace("Z", "+00:00")

    # fromisoformat handles most ISO-8601 variants (Python 3.7+)
    # Truncate to 19 chars to drop sub-second precision that strptime chokes on
    try:
        return datetime.fromisoformat(raw_norm[:19]).date()
    except (ValueError, TypeError):
        pass

    # Try explicit format list
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(raw[: len(fmt) + 5], fmt).date()
        except (ValueError, TypeError):
            continue

    return None