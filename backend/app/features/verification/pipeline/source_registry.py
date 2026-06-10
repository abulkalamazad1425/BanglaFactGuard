"""
app/features/verification/pipeline/source_registry.py
=====================================================
Registry of Bangla news sources and their specific HTML structures for scraping.
"""

from typing import TypedDict

class SourceConfig(TypedDict):
    name: str
    body_selectors: list[str]
    title_selectors: list[str]
    date_selectors: list[str]
    internal_search_url: str
    article_url_patterns: list[str]


SOURCE_REGISTRY: dict[str, SourceConfig] = {
    "prothomalo.com": {
        "name": "প্রথম আলো",
        "body_selectors": [".story-element", ".story-content", "article", "div[data-component='Text']"],
        "title_selectors": ["h1.title", "h1.story-title", "h1"],
        "date_selectors": ["time", ".time", ".published-time"],
        "internal_search_url": "https://www.prothomalo.com/search?q={query}",
        "article_url_patterns": [r"/[a-z-]+/article/", r"/[a-z-]+/[a-z-]+/.*"],
    },
    "bd-pratidin.com": {
        "name": "বাংলাদেশ প্রতিদিন",
        "body_selectors": ["article", ".news-details", ".news-body"],
        "title_selectors": ["h1", "div.news-title"],
        "date_selectors": [".date", ".post-date"],
        "internal_search_url": "https://www.bd-pratidin.com/search?q={query}",
        "article_url_patterns": [r"/news/\d+/\d+/\d+/\d+", r"/[a-z-]+/\d+/\d+/\d+/\d+"],
    },
    "kalerkantho.com": {
        "name": "কালের কণ্ঠ",
        "body_selectors": [".details-txt", "article", ".news-details", ".some-class"],
        "title_selectors": ["h2", "h1", "h1.title"],
        "date_selectors": [".date"],
        "internal_search_url": "https://www.kalerkantho.com/search?q={query}",
        "article_url_patterns": [r"/online/[a-z-]+/\d+/\d+/\d+/\d+", r"/print-edition/[a-z-]+/\d+/\d+/\d+/\d+", r"/[a-z-]+/\d+/\d+/\d+/\d+"],
    },
    "jugantor.com": {
        "name": "যুগান্তর",
        "body_selectors": ["div#myText", ".news-details", ".content-details", "article"],
        "title_selectors": ["h3.font-weight-bolder", "h1", "h1.title"],
        "date_selectors": [".post-date", ".date"],
        "internal_search_url": "https://www.jugantor.com/search?q={query}",
        "article_url_patterns": [r"/[a-z-]+/\d+/\d+/\d+/\d+"],
    },
    "ittefaq.com.bd": {
        "name": "ইত্তেফাক",
        "body_selectors": ["div.dtl_content_block", ".content-details", ".details-content", "article"],
        "title_selectors": ["h1.title", "h1"],
        "date_selectors": [".date", "time"],
        "internal_search_url": "https://www.ittefaq.com.bd/search?q={query}",
        "article_url_patterns": [r"/[a-z-]+/\d+/\d+"],
    },
    "samakal.com": {
        "name": "সমকাল",
        "body_selectors": ["div.description", ".detail-content", "article"],
        "title_selectors": ["h1.detail-title", "h1"],
        "date_selectors": [".date", ".post-date"],
        "internal_search_url": "https://samakal.com/search?q={query}",
        "article_url_patterns": [r"/[a-z-]+/article/\d+"],
    },
    "mzamin.com": {
        "name": "মানবজমিন",
        "body_selectors": [".details-text", ".news-details", "article"],
        "title_selectors": ["h1"],
        "date_selectors": [".date", "time"],
        "internal_search_url": "https://mzamin.com/search.php?q={query}",
        "article_url_patterns": [r"/article\.php\?mzamin=\d+", r"/news/\d+"],
    },
    "dailyjanakantha.com": {
        "name": "জনকণ্ঠ",
        "body_selectors": ["article", ".details-content", ".news-body"],
        "title_selectors": ["h1", "h1.title"],
        "date_selectors": [".date", ".post-date"],
        "internal_search_url": "https://www.dailyjanakantha.com/search?q={query}",
        "article_url_patterns": [r"/news/\d+"],
    },
    "dailyinqilab.com": {
        "name": "ইনকিলাব",
        "body_selectors": [".news-details", "article", ".content"],
        "title_selectors": ["h1", "h1.title"],
        "date_selectors": [".date", "time"],
        "internal_search_url": "https://dailyinqilab.com/search?q={query}",
        "article_url_patterns": [r"/article/\d+", r"/news/\d+"],
    },
    "dailynayadiganta.com": {
        "name": "নয়া দিগন্ত",
        "body_selectors": [".news-content", "article", ".content-details"],
        "title_selectors": ["h1", "h1.title"],
        "date_selectors": [".date", "time"],
        "internal_search_url": "https://www.dailynayadiganta.com/search?q={query}",
        "article_url_patterns": [r"/[a-z-]+/\d+"],
    },
}
