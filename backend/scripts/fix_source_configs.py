"""
One-off maintenance script: repairs verified_sources rows whose
article_url_patterns / body_selectors / internal_search_url drifted out of
sync with the live site after a redesign. See the investigation notes in
the accompanying commit/PR description for how each fix was verified
against the live site.

prothomalo.com is deliberately not touched.

Usage: python scripts/fix_source_configs.py
"""

from __future__ import annotations

import asyncio
import json

import asyncpg

from app.core.config import get_settings

_SETTINGS = get_settings().db


async def main() -> None:
    conn = await asyncpg.connect(
        host=_SETTINGS.host,
        port=_SETTINGS.port,
        database=_SETTINGS.name,
        user=_SETTINGS.user,
        password=_SETTINGS.password,
    )
    try:
        await _fix_mzamin(conn)
        await _fix_kalerkantho(conn)
        await _fix_jugantor(conn)
        await _fix_dailystar(conn)
        await _fix_ittefaq(conn)
        await _fix_dailyinqilab(conn)
        await _fix_dailynayadiganta(conn)
    finally:
        await conn.close()


async def _update(
    conn: asyncpg.Connection,
    canonical_name: str,
    *,
    article_url_patterns: list[str] | None = None,
    body_selectors: list[str] | None = None,
    internal_search_url: str | object = ...,
) -> None:
    sets = []
    params: list = []

    if article_url_patterns is not None:
        params.append(json.dumps(article_url_patterns, ensure_ascii=False))
        sets.append(f"article_url_patterns = ${len(params)}::jsonb")

    if body_selectors is not None:
        params.append(json.dumps(body_selectors, ensure_ascii=False))
        sets.append(f"body_selectors = ${len(params)}::jsonb")

    if internal_search_url is not ...:
        params.append(internal_search_url)
        sets.append(f"internal_search_url = ${len(params)}")

    if not sets:
        return

    params.append(canonical_name)
    sql = (
        f"UPDATE verified_sources SET {', '.join(sets)}, updated_at = now() "
        f"WHERE canonical_name = ${len(params)}"
    )
    result = await conn.execute(sql, *params)
    print(f"{canonical_name}: {result}")


async def _fix_mzamin(conn: asyncpg.Connection) -> None:
    # Site moved from /article.php?mzamin={id} to a clean /article/{id} path.
    await _update(
        conn,
        "mzamin.com",
        article_url_patterns=[
            r"mzamin\.com/article/\d+",
            r"mzamin\.com/article\.php\?mzamin=\d+",
            r"mzamin\.com/news/\d+",
        ],
        # /search.php now returns an empty response; /search is the live endpoint.
        internal_search_url="https://www.mzamin.com/search?q={query}",
    )


async def _fix_kalerkantho(conn: asyncpg.Connection) -> None:
    # Real URLs now carry two category segments before the date
    # (e.g. /multimedia/capital/2026/08/01/12345, /online/country-news/...).
    await _update(
        conn,
        "kalerkantho.com",
        article_url_patterns=[
            r"kalerkantho\.com/online/[^/]+/\d{4}/\d{2}/\d{2}/\d+",
            r"kalerkantho\.com/print-edition/[^/]+/\d{4}/\d{2}/\d{2}/\d+",
            r"kalerkantho\.com/[^/]+/[^/]+/\d{4}/\d{2}/\d{2}/\d+",
            r"kalerkantho\.com/[^/]+/\d{4}/\d{2}/\d{2}/\d+",
        ],
        # The site's own search results are populated client-side via XHR —
        # a plain HTTP GET returns page chrome with no result links.
        internal_search_url=None,
    )


async def _fix_jugantor(conn: asyncpg.Connection) -> None:
    # Body now lives in .detailBody (old #myText / .news-details wrappers
    # are gone) — keep old selectors as harmless fallbacks.
    await _update(
        conn,
        "jugantor.com",
        body_selectors=[
            ".detailBody p",
            "div#myText p",
            "#myText",
            "div[id='myText'] p",
            ".news-details p",
            ".content-details p",
            "div[class*='news-body'] p",
            "article p",
        ],
        # Search results are populated client-side via XHR, same as kalerkantho.
        internal_search_url=None,
    )


async def _fix_dailystar(conn: asyncpg.Connection) -> None:
    # internal_search_url was never configured for this source.
    await _update(
        conn,
        "bangla.thedailystar.net",
        internal_search_url="https://bangla.thedailystar.net/search?q={query}",
    )


async def _fix_ittefaq(conn: asyncpg.Connection) -> None:
    # Real URLs are /{id}/{bangla-slug} — the numeric ID is the first
    # segment, not the end of the string, so the old end-anchored pattern
    # never matched.
    await _update(
        conn,
        "ittefaq.com.bd",
        article_url_patterns=[
            r"ittefaq\.com\.bd/\d{5,}(?:/|$)",
            r"ittefaq\.com\.bd/[a-z-]+/\d{4}-\d{2}-\d{2}/\d+",
            r"ittefaq\.com\.bd/[a-z-]+/\d+",
        ],
    )


async def _fix_dailyinqilab(conn: asyncpg.Connection) -> None:
    # Real URLs are /{category}/news/{id} — old pattern required "news"
    # immediately after the domain, missing the category segment.
    await _update(
        conn,
        "dailyinqilab.com",
        article_url_patterns=[
            r"dailyinqilab\.com/[^/]+/news/\d+",
            r"dailyinqilab\.com/article/\d+",
            r"dailyinqilab\.com/news/\d+",
        ],
    )


async def _fix_dailynayadiganta(conn: asyncpg.Connection) -> None:
    # Site moved to short opaque alphanumeric slugs
    # (/{category}[/{subcategory}]/{slug}/) instead of numeric IDs.
    await _update(
        conn,
        "dailynayadiganta.com",
        article_url_patterns=[
            r"dailynayadiganta\.com/[^/]+/[^/]+/[a-zA-Z0-9]{8,}/?$",
            r"dailynayadiganta\.com/[^/]+/[a-zA-Z0-9]{8,}/?$",
            r"dailynayadiganta\.com/detail/news/\d+",
            r"dailynayadiganta\.com/[^/]+/\d+[a-z]*$",
            r"dailynayadiganta\.com/[^/]+/[a-zA-Z0-9]{6,}$",
        ],
    )


if __name__ == "__main__":
    asyncio.run(main())
