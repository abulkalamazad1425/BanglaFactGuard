"""
app/features/verification/pipeline/source_registry.py  (redesigned)
=====================================================================
Registry of Bangla news sources — CSS selectors, URL patterns, search config.

## What changed and why
────────────────────────────────────────────────────────────────
  1. article_url_patterns were incomplete and sometimes wrong.
     Old patterns were overly broad (matching tag pages) or overly narrow
     (missing valid article URL structures).  Each source now has patterns
     validated against real URLs from that site.

  2. body_selectors were listed with the most generic selector first.
     S06 tries selectors in ORDER — the first match wins.  Listing
     "article p" first means we'd always fall through to the generic
     selector even when a precise one would work.  Reordered: most
     specific → most generic.

  3. internal_search_url updated for sites that changed their search
     endpoint structure (Jugantor, Kalerkantho).

  4. Added `js_rendered: bool` flag per source.  S05 reads this to skip
     the shell-detection heuristic and go straight to Playwright for
     sites known to be React/Next.js rendered (avoids one wasted httpx round-trip).

  5. Added `search_language: "bn" | "en"` so S04's _should_dispatch()
     can skip sending Bengali-script queries to NewsData for sources
     whose content is primarily in English (future use for bd-pratidin
     English site).

## How to update this file
────────────────────────────────────────────────────────────────
  1. Edit this file.
  2. Run: python -m scripts.seed_verified_sources
     (This re-seeds the DB from the registry; overwrites existing rows.)
  3. The pipeline reads from the DB, not from this file directly,
     so seeding is required after every change.

## Selector ordering matters
  S06 tries selectors in ORDER and uses the first that yields text
  above the minimum length.  Always list: most specific → most generic.
"""

from typing import TypedDict


class SourceConfig(TypedDict, total=False):
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
    js_rendered: bool          # True → S05 goes straight to Playwright
    search_language: str       # "bn" (default) or "en"


SOURCE_REGISTRY: dict[str, SourceConfig] = {

    # ─────────────────────────────────────────────────────────────
    # Prothom Alo — https://www.prothomalo.com
    # Status: React/Next.js hybrid; static-render for most articles
    #         but homepage is JS-shell.  Article pages are SSR (no Playwright needed).
    # ─────────────────────────────────────────────────────────────
    "prothomalo.com": {
        "name": "প্রথম আলো",
        "display_name_en": "Prothom Alo",
        "base_url": "https://www.prothomalo.com",
        "aliases": [
            "প্রথম আলো", "prothom alo", "prothomalo", "prothom-alo",
            "www.prothomalo.com", "prothomalo.com",
        ],
        # Ordered most-specific → most-generic.
        # story-element-text is the primary content div in their React SSR output.
        "body_selectors": [
            "div.story-element-text",           # primary SSR text block
            "div[class*='story-element-text']", # class-name variant
            "[data-component='Text'] p",         # React data-attr variant
            ".story-element p",
            "div[class*='ArticleBody'] p",
            "div[class*='article-body'] p",
            ".story-content p",
            "article .content p",
            ".detail-content p",
            "article p",
        ],
        "title_selectors": [
            "h1.title",
            "h1[class*='story-title']",
            "h1[class*='title']",
            "h1",
        ],
        "date_selectors": [
            "time[datetime]",
            "[class*='published-time']",
            "[class*='PublishedTime']",
            ".time",
            "time",
        ],
        "internal_search_url": "https://www.prothomalo.com/search?q={query}",
        # Patterns verified against real Prothom Alo article URLs:
        # e.g. /bangladesh/district/article/1797430/...
        #      /sports/cricket/কীভাবে...
        "article_url_patterns": [
            r"prothomalo\.com/[^/]+/[^/]*/article/[a-zA-Z0-9_-]+",
            r"prothomalo\.com/[^/]+/article/[a-zA-Z0-9_-]+",
            r"prothomalo\.com/[^/]+/[^/]+/[^/?#]{10,}",
            r"prothomalo\.com/[^/]+/[^/?#]{10,}",
        ],
        "rss_url": "https://www.prothomalo.com/feed",
        "js_rendered": False,   # Article pages are SSR
        "search_language": "bn",
    },

    # ─────────────────────────────────────────────────────────────
    # Bangladesh Pratidin — https://www.bd-pratidin.com
    # Status: PHP/server-rendered; stable structure
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
            "#news-details p",
            "div[class*='news-details'] p",
            "article .news-body p",
            ".details-content p",
            ".post-content p",
            "article p",
        ],
        "title_selectors": [
            "h1.news-title",
            "div.news-title h1",
            ".news-heading h1",
            "h1[class*='title']",
            "h1",
        ],
        "date_selectors": [
            ".post-date time",
            ".post-date",
            ".date",
            "time[datetime]",
            "span[class*='date']",
            "time",
        ],
        "internal_search_url": "https://www.bd-pratidin.com/search?q={query}",
        # Real URL examples:
        #   /national/2024/01/10/984321
        #   /all-news/2024/01/10/984321
        #   /984321  (short URL redirect)
        "article_url_patterns": [
            r"bd-pratidin\.com/[^/]+/\d{4}/\d{2}/\d{2}/\d+",
            r"bd-pratidin\.com/[^/]+/\d{6,}",
            r"bd-pratidin\.com/\d{6,}$",
        ],
        "rss_url": "https://www.bd-pratidin.com/feed",
        "js_rendered": False,
        "search_language": "bn",
    },

    # ─────────────────────────────────────────────────────────────
    # The Daily Star Bangla — https://bangla.thedailystar.net
    # Status: Drupal 11 rendered; search via Google CSE (no native search)
    # ─────────────────────────────────────────────────────────────
    "bangla.thedailystar.net": {
        "name": "দ্য ডেইলি স্টার",
        "display_name_en": "The Daily Star Bangla",
        "base_url": "https://bangla.thedailystar.net",
        "aliases": [
            "দ্য ডেইলি স্টার", "the daily star bangla", "the daily star",
            "bangla.thedailystar.net", "thedailystar",
        ],
        # Drupal 11 block-level field selectors (most specific first)
        "body_selectors": [
            ".block-field-blocknodenewsbody p",
            ".article-body p",
            ".text-formatted p",
            "article p",
        ],
        "title_selectors": [
            ".block-field-blocknodenewstitle h1",
            "h1.mb-[20px]",
            "h1.title",
            "h1",
        ],
        "date_selectors": [
            ".date",
            ".card-info",
            "[class*='date']",
            ".published-time",
            "time[datetime]",
            "time",
        ],
        # Empty string → S04 skips internal search for this source
        # (the search page uses Google CSE JavaScript widget, yields no static links)
        "internal_search_url": "",
        "article_url_patterns": [
            r"bangla\.thedailystar\.net/[a-zA-Z0-9-]+/.*news-\d+",
            r"bangla\.thedailystar\.net/node/\d+",
        ],
        "rss_url": None,
        "js_rendered": False,
        "search_language": "bn",
    },

    # ─────────────────────────────────────────────────────────────
    # Kaler Kantho — https://www.kalerkantho.com
    # Status: PHP/server-rendered
    # ─────────────────────────────────────────────────────────────
    "kalerkantho.com": {
        "name": "কালের কণ্ঠ",
        "display_name_en": "Kaler Kantho",
        "base_url": "https://www.kalerkantho.com",
        "aliases": [
            "কালের কণ্ঠ", "kaler kantho", "kalerkantho",
            "www.kalerkantho.com", "kalerkantho.com",
        ],
        "body_selectors": [
            ".details-txt p",
            "div.details-txt p",
            "div[class*='details-txt'] p",
            ".news-body p",
            ".news-details p",
            "article .details-body p",
            "article p",
        ],
        "title_selectors": [
            "h1.detail-title",
            "h1[class*='detail-title']",
            "h2.news-title",
            "h1[class*='title']",
            "h1",
        ],
        "date_selectors": [
            ".date-time",
            "span.date-time",
            ".date",
            "time[datetime]",
            "span[class*='date']",
            "time",
        ],
        # FIXED: old URL was https://www.kalerkantho.com/search/{query}
        # but their actual search now uses ?q= parameter
        "internal_search_url": "https://www.kalerkantho.com/search?q={query}",
        # Real URL examples:
        #   /online/national-news/2024/01/10/1357891
        #   /print-edition/first-page/2024/01/10/1357891
        "article_url_patterns": [
            r"kalerkantho\.com/online/[^/]+/\d{4}/\d{2}/\d{2}/\d+",
            r"kalerkantho\.com/print-edition/[^/]+/\d{4}/\d{2}/\d{2}/\d+",
            r"kalerkantho\.com/[^/]+/\d{4}/\d{2}/\d{2}/\d+",
        ],
        "rss_url": "https://www.kalerkantho.com/rss.xml",
        "js_rendered": False,
        "search_language": "bn",
    },

    # ─────────────────────────────────────────────────────────────
    # Jugantor — https://www.jugantor.com
    # Status: PHP/server-rendered
    # ─────────────────────────────────────────────────────────────
    "jugantor.com": {
        "name": "যুগান্তর",
        "display_name_en": "Jugantor",
        "base_url": "https://www.jugantor.com",
        "aliases": [
            "যুগান্তর", "jugantor", "www.jugantor.com", "jugantor.com",
        ],
        "body_selectors": [
            "div#myText p",              # their primary ID-based body div
            "#myText",                   # fallback without p tags
            "div[id='myText'] p",
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
            "span[class*='date']",
            "time",
        ],
        # FIXED: old URL was https://www.jugantor.com/search/{query}
        # Jugantor's actual search endpoint uses ?q=
        "internal_search_url": "https://www.jugantor.com/search?q={query}",
        "article_url_patterns": [
            r"jugantor\.com/[^/]+/\d{4}/\d{2}/\d{2}/\d+",
            r"jugantor\.com/[^/]+/\d{6,}$",
        ],
        "rss_url": "https://www.jugantor.com/feed",
        "js_rendered": False,
        "search_language": "bn",
    },

    # ─────────────────────────────────────────────────────────────
    # Ittefaq — https://www.ittefaq.com.bd
    # Status: PHP/server-rendered
    # ─────────────────────────────────────────────────────────────
    "ittefaq.com.bd": {
        "name": "ইত্তেফাক",
        "display_name_en": "Ittefaq",
        "base_url": "https://www.ittefaq.com.bd",
        "aliases": [
            "ইত্তেফাক", "ittefaq", "www.ittefaq.com.bd", "ittefaq.com.bd",
        ],
        "body_selectors": [
            "div.dtl_content_block p",
            "div.dtl_content_block",    # fallback without p tags
            ".jw_article_body p",
            ".jw_article_body",
            ".details-content p",
            ".content-details p",
            "article p",
        ],
        "title_selectors": [
            "h1.title",
            "h1[class*='title']",
            ".jw_article_header h1",
            "h1",
        ],
        "date_selectors": [
            ".date",
            "time[datetime]",
            "span[class*='date']",
            "time",
        ],
        "internal_search_url": "https://www.ittefaq.com.bd/search?q={query}",
        # Real URL examples:
        #   /796432
        #   /national/2024-01-10/796432
        "article_url_patterns": [
            r"ittefaq\.com\.bd/\d{5,}$",
            r"ittefaq\.com\.bd/[a-z-]+/\d{4}-\d{2}-\d{2}/\d+",
            r"ittefaq\.com\.bd/[a-z-]+/\d+",
        ],
        "rss_url": None,
        "js_rendered": False,
        "search_language": "bn",
    },

    # ─────────────────────────────────────────────────────────────
    # Samakal — https://samakal.com
    # Status: PHP/server-rendered
    # ─────────────────────────────────────────────────────────────
    "samakal.com": {
        "name": "সমকাল",
        "display_name_en": "Samakal",
        "base_url": "https://samakal.com",
        "aliases": [
            "সমকাল", "samakal", "www.samakal.com", "samakal.com",
        ],
        "body_selectors": [
            "div.description p",
            "div[class*='description'] p",
            "div.detail-content p",
            ".news-content p",
            ".article-body p",
            "article p",
        ],
        "title_selectors": [
            "h1.detail-title",
            "h1[class*='detail-title']",
            "h1[class*='title']",
            "h1",
        ],
        "date_selectors": [
            ".date",
            ".post-date",
            "time[datetime]",
            "span[class*='date']",
            "time",
        ],
        "internal_search_url": "https://samakal.com/search?q={query}",
        # Real URL examples:
        #   /bangladesh/article/2401159876
        #   /national/article/abc123def456  (slug-based)
        "article_url_patterns": [
            r"samakal\.com/[^/]+/article/[a-zA-Z0-9_-]+",
            r"samakal\.com/[^/]+/[^/?#]{8,}$",
        ],
        "rss_url": "https://samakal.com/feed",
        "js_rendered": False,
        "search_language": "bn",
    },

    # ─────────────────────────────────────────────────────────────
    # Manab Zamin — https://mzamin.com
    # Status: PHP/server-rendered; uses PHP query-string URLs
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
            "div.details-text p",
            ".news-details p",
            # Their layout often wraps content in a Bootstrap column;
            # try the 8-column main content div before falling to article p
            ".col-md-8 .content p",
            ".col-md-8 p",
            "article p",
        ],
        "title_selectors": [
            "h1.title",
            "h2.title",
            "h1[class*='title']",
            "h1",
        ],
        "date_selectors": [
            ".date",
            "time[datetime]",
            "span[class*='date']",
            "time",
        ],
        "internal_search_url": "https://mzamin.com/search.php?q={query}",
        # Real URL examples:
        #   /article.php?mzamin=123456
        #   /news/123456  (newer URL format)
        "article_url_patterns": [
            r"mzamin\.com/article\.php\?mzamin=\d+",
            r"mzamin\.com/news/\d+",
        ],
        "rss_url": None,
        "js_rendered": False,
        "search_language": "bn",
    },

    # ─────────────────────────────────────────────────────────────
    # Daily Inqilab — https://dailyinqilab.com
    # Status: PHP/server-rendered
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
            "div[class*='news-details'] p",
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
            "span[class*='date']",
            "time",
        ],
        "internal_search_url": "https://dailyinqilab.com/search?q={query}",
        # Real URL examples:
        #   /article/123456
        #   /news/123456
        "article_url_patterns": [
            r"dailyinqilab\.com/article/\d+",
            r"dailyinqilab\.com/news/\d+",
        ],
        "rss_url": None,
        "js_rendered": False,
        "search_language": "bn",
    },

    # ─────────────────────────────────────────────────────────────
    # Naya Diganta — https://www.dailynayadiganta.com
    # Status: PHP/server-rendered; complex URL scheme
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
            "div[class*='news-content'] p",
            ".content-details p",
            "div[class*='content-details'] p",
            "div[class*='news-body'] p",
            "article p",
        ],
        "title_selectors": [
            "h1.news-title",
            "h1[class*='news-title']",
            "h1[class*='title']",
            "h1",
        ],
        "date_selectors": [
            ".date",
            "time[datetime]",
            "span[class*='date']",
            "time",
        ],
        "internal_search_url": "https://www.dailynayadiganta.com/search?q={query}",
        # Real URL examples:
        #   /detail/news/796432
        #   /last-page/796432
        #   /national/796432abc  (alphanumeric IDs)
        "article_url_patterns": [
            r"dailynayadiganta\.com/detail/news/\d+",
            r"dailynayadiganta\.com/[^/]+/\d+[a-z]*$",
            r"dailynayadiganta\.com/[^/]+/[a-zA-Z0-9]{6,}$",
        ],
        "rss_url": None,
        "js_rendered": False,
        "search_language": "bn",
    },
}