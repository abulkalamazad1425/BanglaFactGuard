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
from app.shared.utils.dates import ParsedPublication, parse_publication
from app.shared.utils.text_cleaner import clean_extracted_text, clean_title

logger = structlog.get_logger(__name__)
_SETTINGS = get_settings()


_BANGLA_TO_ARABIC = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")

_BANGLA_MONTHS = {
    "জানুয়ারি": "January",
    "ফেব্রুয়ারি": "February",
    "মার্চ": "March",
    "এপ্রিল": "April",
    "মে": "May",
    "জুন": "June",
    "জুলাই": "July",
    "আগস্ট": "August",
    "সেপ্টেম্বর": "September",
    "অক্টোবর": "October",
    "নভেম্বর": "November",
    "ডিসেম্বর": "December",
    "জানু": "January",
    "ফেব্রু": "February",
    "সেপ্টে": "September",
    "অক্টো": "October",
    "নভে": "November",
    "ডিসে": "December",
}


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

    stage_id = PipelineStageID.S06_ARTICLE_EXTRACTOR

    def __init__(self, cache_service: CacheService) -> None:
        self._cache = cache_service
        self._min_body_length = _SETTINGS.search.min_body_length_chars

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
                url,
                html,
                url_to_candidate,
                normalized_source,
                source_config,
            )
            for url, html in raw_html_cache.items()
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        extracted: list[RankedArticleSchema] = []
        extraction_errors = 0
        for (url, _), result in zip(raw_html_cache.items(), results):
            if isinstance(result, RankedArticleSchema):
                if result.has_body or result.title:
                    extracted.append(result)
                else:
                    context.failed_extraction_urls.append(url)
                    extraction_errors += 1
            elif isinstance(result, Exception):
                logger.warning(
                    "s06_extraction_exception", url=url[:80], error=str(result)
                )
                context.failed_extraction_urls.append(url)
                extraction_errors += 1

        context.extraction_attempted += len(raw_html_cache)
        context.extraction_errors += extraction_errors
        context.extracted_articles = extracted
        logger.info(
            "s06_extraction_complete",
            attempted=len(raw_html_cache),
            succeeded=len(extracted),
            failed=len(context.failed_extraction_urls),
        )
        return context

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
        use_config = (
            bool(source_config) and bool(url_domain) and (url_domain == src_domain)
        )
        config = source_config if use_config else None

        title: str | None = None
        body: str | None = None
        author: str | None = None
        method = ExtractionMethod.BEAUTIFULSOUP

        try:
            soup = BeautifulSoup(html, "lxml")
        except Exception:
            soup = BeautifulSoup(html, "html.parser")

        # datePublished, with provenance and tz handling, found independently
        # of body extraction. (Previously the date was only looked for on the
        # fallback paths, so a page whose title/body came from site selectors
        # returned early with no date at all - and the date check could only
        # ever report INCOMPLETE for it.) dateModified and crawl dates are
        # never used.
        published = self._find_publication(soup, config)

        if config:

            for sel in config.get("title_selectors", []):
                el = self._safe_select_one(soup, sel)
                if el:
                    t = el.get_text(strip=True)
                    if t and len(t) > 5:
                        title = t
                        break

            for sel in config.get("body_selectors", []):

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
                                    for p in p_tags
                                    if len(p.get_text(strip=True)) > 10
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
                        self._selector_misses[sel] = 0
                        break
                    else:

                        self._selector_misses[sel] = (
                            self._selector_misses.get(sel, 0) + 1
                        )
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

        if title and body and len(body) >= self._min_body_length:
            return self._build_result(
                url, title, body, author, published, method, provider, candidate, soup
            )

        if not body or len(body) < self._min_body_length:
            for script in soup.find_all("script", type="application/ld+json"):
                try:
                    data = json.loads(script.string or "")
                    items = data if isinstance(data, list) else [data]
                    for item in items:
                        if not isinstance(item, dict):
                            continue
                        if item.get("@type") not in (
                            "NewsArticle",
                            "Article",
                            "ReportageNewsArticle",
                            "WebPage",
                        ):
                            continue
                        ld_body = item.get("articleBody", "")
                        if ld_body and len(ld_body) >= self._min_body_length:
                            title = title or item.get("headline")
                            body = ld_body
                            author_data = item.get("author")
                            if isinstance(author_data, dict) and not author:
                                author = author_data.get("name")
                            elif (
                                isinstance(author_data, list)
                                and author_data
                                and not author
                            ):
                                author = author_data[0].get("name")
                            method = ExtractionMethod.JSON_LD
                            break
                except Exception:
                    continue
                if body and len(body) >= self._min_body_length:
                    break

        if not body or len(body) < self._min_body_length:
            t_title, t_body, t_author, t_date = self._extract_trafilatura(url, html)
            if t_body and len(t_body) >= self._min_body_length:
                title = title or t_title
                body = t_body
                author = author or t_author
                method = ExtractionMethod.TRAFILATURA

        if not body or len(body) < self._min_body_length:
            try:
                doc = Document(html)
                r_html = doc.summary()
                r_body = BeautifulSoup(r_html, "html.parser").get_text(
                    separator="\n", strip=True
                )
                if r_body and len(r_body) >= self._min_body_length:
                    title = title or doc.title()
                    body = r_body
                    method = ExtractionMethod.READABILITY
            except Exception:
                pass

        if not body or len(body) < self._min_body_length:
            bs_title, bs_body, bs_author, bs_date = self._extract_bs4(url, html, config)
            if bs_body and len(bs_body) > len(body or ""):
                title = title or bs_title
                body = bs_body
                author = author or bs_author
                method = ExtractionMethod.BEAUTIFULSOUP

        if not title:
            for prop in ["og:title", "twitter:title"]:
                meta = soup.find("meta", property=prop) or soup.find(
                    "meta", attrs={"name": prop}
                )
                if meta and meta.get("content"):
                    title = meta["content"]
                    break
            if not title and soup.title:
                title = soup.title.get_text(strip=True)

        if not body or len(body) < 100:
            for prop in ["og:description", "description"]:
                meta = soup.find("meta", property=prop) or soup.find(
                    "meta", attrs={"name": prop}
                )
                if meta and meta.get("content") and len(meta["content"]) > 100:
                    body = meta["content"]
                    method = ExtractionMethod.OPENGRAPH
                    break

        return self._build_result(
            url, title, body, author, published, method, provider, candidate, soup
        )

    def _find_publication(self, soup, config) -> tuple[ParsedPublication | None, str | None]:
        """(parsed publication, provenance label). Priority: the outlet's own
        date selectors, JSON-LD datePublished, publication meta tags,
        <time itemprop=datePublished>."""
        if config:
            for sel in config.get("date_selectors", []):
                el = self._safe_select_one(soup, sel)
                if el:
                    parsed = parse_publication(el.get("datetime") or el.get_text(strip=True))
                    if parsed:
                        return parsed, f"selector:{sel}"[:80]

        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or script.get_text() or "")
            except Exception:
                continue
            for item in _iter_ld_items(data):
                raw = item.get("datePublished")
                if raw:
                    parsed = parse_publication(str(raw))
                    if parsed:
                        return parsed, "json_ld.datePublished"

        for attrs, label in (
            ({"property": "article:published_time"}, "meta.article:published_time"),
            ({"property": "og:article:published_time"}, "meta.og:article:published_time"),
            ({"itemprop": "datePublished"}, "meta.itemprop.datePublished"),
            ({"name": "publish_date"}, "meta.publish_date"),
            ({"name": "pubdate"}, "meta.pubdate"),
            ({"name": "dc.date.issued"}, "meta.dc.date.issued"),
        ):
            meta = soup.find("meta", attrs=attrs)
            if meta and meta.get("content"):
                parsed = parse_publication(meta["content"])
                if parsed:
                    return parsed, label

        time_el = soup.find("time", attrs={"itemprop": "datePublished"})
        if time_el:
            parsed = parse_publication(time_el.get("datetime") or time_el.get_text(strip=True))
            if parsed:
                return parsed, "time.itemprop.datePublished"
        return None, None

    def _build_result(
        self, url, title, body, author, published, method, provider, candidate, soup
    ) -> RankedArticleSchema:
        parsed, pub_source = published

        if title:
            title = _TITLE_SUFFIX_RE.sub("", title).strip()

        if (
            candidate
            and candidate.title_snippet
            and (not title or title.strip().lower() in ("google news", ""))
        ):
            title = candidate.title_snippet

        return RankedArticleSchema(
            url=url,
            title=clean_title(title),
            body=(
                clean_extracted_text(body, min_length=self._min_body_length)
                if body
                else None
            ),
            author=author,
            published_date=parsed.local_date if parsed else None,
            published_at=parsed.published_at if parsed else None,
            published_date_source=pub_source if parsed else None,
            published_tz_assumed=parsed.tz_assumed if parsed else False,
            rank_score=0.0,
            search_provider=provider,
            extraction_method=method,
        )

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

    def _extract_trafilatura(self, url: str, html: str):
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
            meta = trafilatura.extract_metadata(html, url=url)
            title = author = None
            if meta:
                title = meta.title or None
                author = meta.author or None
            # meta.date is deliberately ignored: trafilatura returns the most
            # recent date it finds (often dateModified), and publication date
            # is only ever taken from datePublished sources (_find_publication).
            return title, body, author, None
        except Exception as exc:
            logger.debug("s06_trafilatura_failed", url=url[:80], error=str(exc))
            return None, None, None, None

    def _extract_bs4(self, url: str, html: str, config: dict | None):
        try:
            soup = BeautifulSoup(html, "lxml")
        except Exception:
            soup = BeautifulSoup(html, "html.parser")

        title: str | None = None
        og = soup.find("meta", property="og:title")
        if og and og.get("content"):
            title = og["content"]
        elif soup.find("h1"):
            title = soup.find("h1").get_text(strip=True)
        elif soup.title:
            title = soup.title.get_text(strip=True)

        author: str | None = None
        a_meta = soup.find("meta", attrs={"name": "author"})
        if a_meta and a_meta.get("content"):
            author = a_meta["content"]

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

        for tag in soup.find_all(
            ["nav", "header", "footer", "aside", "script", "style", "noscript"]
        ):
            tag.decompose()

        body: str | None = None

        if config:
            for sel in config.get("body_selectors", []):
                els = self._safe_select(soup, sel)
                if els:
                    parts = [el.get_text(separator="\n", strip=True) for el in els]
                    combined = "\n".join(p for p in parts if p)
                    if len(combined) > len(body or ""):
                        body = combined

        if not body or len(body) < self._min_body_length:
            article_el = soup.find("article")
            if article_el:
                body = article_el.get_text(separator="\n", strip=True)

        if not body or len(body) < self._min_body_length:
            for pattern in [
                "article-body",
                "article_body",
                "post-content",
                "entry-content",
                "news-body",
                "story-body",
                "news-content",
                "details-body",
                "dtl_content_block",
                "jw_article_body",
                "content-body",
                "news-details",
                "details-text",
                "details-txt",
            ]:
                divs = soup.find_all(
                    ["div", "section"],
                    class_=lambda c, p=pattern: c and p in c.split(),
                )
                if divs:
                    candidate_text = "\n".join(
                        d.get_text(separator="\n", strip=True) for d in divs
                    )
                    if len(candidate_text) > len(body or ""):
                        body = candidate_text
                    break

        if not body or len(body) < self._min_body_length:
            paras = [
                p.get_text(strip=True)
                for p in soup.find_all("p")
                if len(p.get_text(strip=True)) > 40
            ]
            body = "\n".join(paras)
        return title, body or None, author, pub_date


def _iter_ld_items(data):
    """Yield every dict in a JSON-LD payload, including @graph members."""
    stack = [data]
    while stack:
        cur = stack.pop()
        if isinstance(cur, list):
            stack.extend(cur)
        elif isinstance(cur, dict):
            yield cur
            graph = cur.get("@graph")
            if graph:
                stack.append(graph)


def _parse_date(raw: str | None) -> date | None:
    if not raw:
        return None
    raw = raw.strip()
    raw = raw.translate(_BANGLA_TO_ARABIC)
    for bn, en in _BANGLA_MONTHS.items():
        raw = raw.replace(bn, en)

    raw_norm = raw.replace("Z", "+00:00")

    try:
        return datetime.fromisoformat(raw_norm[:19]).date()
    except (ValueError, TypeError):
        pass

    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(raw[: len(fmt) + 5], fmt).date()
        except (ValueError, TypeError):
            continue

    return None
