"""
app/features/verification/pipeline/source_registry.py
=====================================================
Registry of Bangla news sources and their specific HTML structures for scraping.

This is the canonical reference for:
  - body_selectors:          CSS selectors to extract article body text
  - title_selectors:         CSS selectors to extract article headline
  - date_selectors:          CSS selectors / attributes to extract publish date
  - internal_search_url:     Site's own search endpoint (query as {query})
  - article_url_patterns:    Regex patterns that match only article URLs (not tags/categories)

These values are seeded into the verified_sources DB table on startup via
the seed_verified_sources management command. The pipeline reads from the DB
(not from this file directly) so any update here requires re-seeding.

Selector ordering matters — the extractor tries each selector in order and
uses the first one that yields non-empty text above the minimum length.
"""

from typing import TypedDict


class SourceConfig(TypedDict):
    name: str
    display_name_en: str
    base_url: str
    aliases: list[str]
    body_selectors: list[str]
    title_selectors: list[str]
    date_selectors: list[str]
    internal_search_url: str
    article_url_patterns: list[str]
    rss_url: str | None


SOURCE_REGISTRY: dict[str, SourceConfig] = {

    # ─────────────────────────────────────────────────────────────
    # Prothom Alo — https://www.prothomalo.com
    # ─────────────────────────────────────────────────────────────
    "prothomalo.com": {
        "name": "প্রথম আলো",
        "display_name_en": "Prothom Alo",
        "base_url": "https://www.prothomalo.com",
        "aliases": [
            "প্রথম আলো", "prothom alo", "prothomalo", "prothom-alo",
            "www.prothomalo.com", "prothomalo.com",
        ],
        # Prothom Alo renders story blocks inside `.story-element` divs;
        # each div may contain <p> tags. The `[data-component="Text"]` selector
        # covers their React-rendered text blocks.
        "body_selectors": [
            "div.story-element-text",
            "[data-component='Text'] p",
            ".story-element p",
            ".story-content p",
            "article .content p",
            "div[class*='ArticleBody'] p",
            "div[class*='story-body'] p",
            ".detail-content p",
            "article p",
        ],
        "title_selectors": [
            "h1.title",
            "h1.story-title",
            "h1[class*='title']",
            "h1",
        ],
        "date_selectors": [
            "time[datetime]",
            "time",
            "[class*='published-time']",
            "[class*='PublishedTime']",
            ".time",
        ],
        "internal_search_url": "https://www.prothomalo.com/search?q={query}",
        "article_url_patterns": [
            r"prothomalo\.com/[^/]+/article/[a-zA-Z0-9_-]+",
            r"prothomalo\.com/[^/]+/[^/]+/[a-zA-Z0-9_-]+",
            r"prothomalo\.com/[^/]+/[^/?#]{8,}",
        ],
        "rss_url": "https://www.prothomalo.com/feed",
    },

    # ─────────────────────────────────────────────────────────────
    # Bangladesh Pratidin — https://www.bd-pratidin.com
    # ─────────────────────────────────────────────────────────────
    "bd-pratidin.com": {
        "name": "বাংলাদেশ প্রতিদিন",
        "display_name_en": "Bangladesh Pratidin",
        "base_url": "https://www.bd-pratidin.com",
        "aliases": [
            "বাংলাদেশ প্রতিদিন", "bangladesh pratidin", "bd pratidin",
            "bd-pratidin", "www.bd-pratidin.com", "bd-pratidin.com",
        ],
        "body_selectors": [
            ".news-details p",
            "article .news-body p",
            ".details-content p",
            ".post-content p",
            "article p",
            ".content-details p",
        ],
        "title_selectors": [
            "h1.news-title",
            "div.news-title h1",
            "h1[class*='title']",
            "h1",
        ],
        "date_selectors": [
            ".post-date",
            ".date",
            "time[datetime]",
            "time",
            "span[class*='date']",
        ],
        "internal_search_url": "https://www.bd-pratidin.com/search?q={query}",
        "article_url_patterns": [
            # Numeric article ID at the end — the most reliable pattern
            r"bd-pratidin\.com/[^/]+/\d{4}/\d{2}/\d{2}/\d+",  # category/YYYY/MM/DD/ID
            r"bd-pratidin\.com/[^/]+/\d{6,}",                  # category/ID (short URL)
            r"bd-pratidin\.com/\d{6,}",                         # bare /ID
        ],
        "rss_url": "https://www.bd-pratidin.com/feed",
    },

    # ─────────────────────────────────────────────────────────────
    # Kaler Kantho — https://www.kalerkantho.com
    # ─────────────────────────────────────────────────────────────
    "kalerkantho.com": {
        "name": "কালের কণ্ঠ",
        "display_name_en": "Kaler Kantho",
        "base_url": "https://www.kalerkantho.com",
        "aliases": [
            "কালের কণ্ঠ", "kaler kantho", "kalerkantho",
            "www.kalerkantho.com", "kalerkantho.com",
        ],
        # Kaler Kantho wraps article text in .details-txt; sometimes in .news-details
        "body_selectors": [
            ".details-txt p",
            ".news-body p",
            ".news-details p",
            "article .details-body p",
            "div[class*='details-txt'] p",
            "article p",
        ],
        "title_selectors": [
            "h1.detail-title",
            "h2.news-title",
            "h1[class*='title']",
            "h2[class*='title']",
            "h1",
        ],
        "date_selectors": [
            ".date-time",
            ".date",
            "time[datetime]",
            "time",
            "span[class*='date']",
        ],
        "internal_search_url": "https://www.kalerkantho.com/search/{query}",
        "article_url_patterns": [
            r"kalerkantho\.com/online/[^/]+/\d{4}/\d{2}/\d{2}/\d+",
            r"kalerkantho\.com/print-edition/[^/]+/\d{4}/\d{2}/\d{2}/\d+",
            r"kalerkantho\.com/[^/]+/\d{4}/\d{2}/\d{2}/\d+",
        ],
        "rss_url": "https://www.kalerkantho.com/rss.xml",
    },

    # ─────────────────────────────────────────────────────────────
    # Jugantor — https://www.jugantor.com
    # ─────────────────────────────────────────────────────────────
    "jugantor.com": {
        "name": "যুগান্তর",
        "display_name_en": "Jugantor",
        "base_url": "https://www.jugantor.com",
        "aliases": [
            "যুগান্তর", "jugantor", "www.jugantor.com", "jugantor.com",
        ],
        # Jugantor uses #myText as the article body container
        "body_selectors": [
            "div#myText p",
            ".news-details p",
            ".content-details p",
            "div[class*='news-body'] p",
            "article p",
        ],
        "title_selectors": [
            "h3.font-weight-bolder",
            "h1.news-title",
            "h1[class*='title']",
            "h1",
        ],
        "date_selectors": [
            ".post-date",
            ".date",
            "time[datetime]",
            "time",
            "span[class*='date']",
        ],
        "internal_search_url": "https://www.jugantor.com/search/{query}",
        "article_url_patterns": [
            r"jugantor\.com/[^/]+/\d{4}/\d{2}/\d{2}/\d+",
            r"jugantor\.com/[^/]+/\d{6,}",
        ],
        "rss_url": "https://www.jugantor.com/feed",
    },

    # ─────────────────────────────────────────────────────────────
    # Ittefaq — https://www.ittefaq.com.bd
    # ─────────────────────────────────────────────────────────────
    "ittefaq.com.bd": {
        "name": "ইত্তেফাক",
        "display_name_en": "Ittefaq",
        "base_url": "https://www.ittefaq.com.bd",
        "aliases": [
            "ইত্তেফাক", "ittefaq", "www.ittefaq.com.bd", "ittefaq.com.bd",
        ],
        # Ittefaq uses dtl_content_block and jw_article_body for news body
        "body_selectors": [
            "div.dtl_content_block p",
            ".jw_article_body p",
            ".details-content p",
            ".content-details p",
            "article p",
        ],
        "title_selectors": [
            "h1.title",
            "h1[class*='title']",
            "h1",
        ],
        "date_selectors": [
            ".date",
            "time[datetime]",
            "time",
            "span[class*='date']",
        ],
        "internal_search_url": "https://www.ittefaq.com.bd/search?q={query}",
        "article_url_patterns": [
            r"ittefaq\.com\.bd/\d+",
            r"ittefaq\.com\.bd/[a-z-]+/\d+/\d+",
        ],
        "rss_url": None,
    },

    # ─────────────────────────────────────────────────────────────
    # Samakal — https://samakal.com
    # ─────────────────────────────────────────────────────────────
    "samakal.com": {
        "name": "সমকাল",
        "display_name_en": "Samakal",
        "base_url": "https://samakal.com",
        "aliases": [
            "সমকাল", "samakal", "www.samakal.com", "samakal.com",
        ],
        # Samakal uses div.description for article body
        "body_selectors": [
            "div.description p",
            ".detail-content p",
            ".news-content p",
            "div[class*='description'] p",
            "article p",
        ],
        "title_selectors": [
            "h1.detail-title",
            "h1[class*='title']",
            "h1",
        ],
        "date_selectors": [
            ".date",
            ".post-date",
            "time[datetime]",
            "time",
            "span[class*='date']",
        ],
        "internal_search_url": "https://samakal.com/search?q={query}",
        "article_url_patterns": [
            r"samakal\.com/[^/]+/article/[a-zA-Z0-9_-]+",
            r"samakal\.com/[^/]+/[^/?#]{8,}",
        ],
        "rss_url": "https://samakal.com/feed",
    },

    # ─────────────────────────────────────────────────────────────
    # Manab Zamin — https://mzamin.com
    # ─────────────────────────────────────────────────────────────
    "mzamin.com": {
        "name": "মানবজমিন",
        "display_name_en": "Manab Zamin",
        "base_url": "https://mzamin.com",
        "aliases": [
            "মানবজমিন", "manab zamin", "manabzamin", "mzamin",
            "www.mzamin.com", "mzamin.com",
        ],
        "body_selectors": [
            ".details-text p",
            ".news-details p",
            ".col-md-8 p",
            "article p",
        ],
        "title_selectors": [
            "h1.title",
            "h1[class*='title']",
            "h1",
        ],
        "date_selectors": [
            ".date",
            "time[datetime]",
            "time",
            "span[class*='date']",
        ],
        "internal_search_url": "https://mzamin.com/search.php?q={query}",
        "article_url_patterns": [
            r"mzamin\.com/article\.php\?mzamin=\d+",
            r"mzamin\.com/news/\d+",
        ],
        "rss_url": None,
    },

    # ─────────────────────────────────────────────────────────────
    # Daily Inqilab — https://dailyinqilab.com
    # ─────────────────────────────────────────────────────────────
    "dailyinqilab.com": {
        "name": "ইনকিলাব",
        "display_name_en": "Daily Inqilab",
        "base_url": "https://dailyinqilab.com",
        "aliases": [
            "ইনকিলাব", "inqilab", "daily inqilab", "dailyinqilab",
            "www.dailyinqilab.com", "dailyinqilab.com",
        ],
        "body_selectors": [
            ".news-details p",
            ".content p",
            "article .news-body p",
            "article p",
        ],
        "title_selectors": [
            "h1.title",
            "h1[class*='title']",
            "h1",
        ],
        "date_selectors": [
            ".date",
            "time[datetime]",
            "time",
            "span[class*='date']",
        ],
        "internal_search_url": "https://dailyinqilab.com/search?q={query}",
        "article_url_patterns": [
            r"dailyinqilab\.com/article/\d+",
            r"dailyinqilab\.com/news/\d+",
        ],
        "rss_url": None,
    },

    # ─────────────────────────────────────────────────────────────
    # Naya Diganta — https://www.dailynayadiganta.com
    # ─────────────────────────────────────────────────────────────
    "dailynayadiganta.com": {
        "name": "নয়া দিগন্ত",
        "display_name_en": "Naya Diganta",
        "base_url": "https://www.dailynayadiganta.com",
        "aliases": [
            "নয়া দিগন্ত", "naya diganta", "nayadiganta", "daily nayadiganta",
            "www.dailynayadiganta.com", "dailynayadiganta.com",
        ],
        "body_selectors": [
            ".news-content p",
            ".content-details p",
            "div[class*='news-body'] p",
            "article p",
        ],
        "title_selectors": [
            "h1.news-title",
            "h1[class*='title']",
            "h1",
        ],
        "date_selectors": [
            ".date",
            "time[datetime]",
            "time",
            "span[class*='date']",
        ],
        "internal_search_url": "https://www.dailynayadiganta.com/search?q={query}",
        "article_url_patterns": [
            r"dailynayadiganta\.com/[^/]+/[a-zA-Z0-9]+/?$",
            r"dailynayadiganta\.com/[^/]+/\d+",
            r"dailynayadiganta\.com/detail/news/\d+",
        ],
        "rss_url": None,
    },
}
