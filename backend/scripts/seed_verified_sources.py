from __future__ import annotations

import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


import app.features.sources.models
import app.features.verification.models
import app.features.articles.models

from sqlalchemy import select
from app.db.engine import AsyncSessionLocal
from app.features.sources.models import VerifiedSource
from app.features.verification.pipeline.source_registry import SOURCE_REGISTRY


async def seed_verified_sources() -> None:
    print("=" * 60)
    print("Seeding verified_sources table from SOURCE_REGISTRY...")
    print("=" * 60)

    async with AsyncSessionLocal() as session:
        created = 0
        updated = 0

        for canonical_name, config in SOURCE_REGISTRY.items():

            result = await session.execute(
                select(VerifiedSource).where(
                    VerifiedSource.canonical_name == canonical_name
                )
            )
            existing = result.scalar_one_or_none()

            if existing:

                existing.display_name = config["name"]
                existing.body_selectors = config["body_selectors"]
                existing.title_selectors = config["title_selectors"]
                existing.date_selectors = config["date_selectors"]
                existing.internal_search_url = config["internal_search_url"]
                existing.article_url_patterns = config["article_url_patterns"]
                existing.base_url = config["base_url"]

                current_aliases: list[str] = existing.aliases or []
                registry_aliases: list[str] = config.get("aliases", [])
                merged = list(set(current_aliases) | set(registry_aliases))
                existing.aliases = merged

                if existing.rss_url is None and config.get("rss_url"):
                    existing.rss_url = config["rss_url"]

                session.add(existing)
                updated += 1
                en_name = config.get("display_name_en", canonical_name)
                print(f"  [UPDATED] {canonical_name} ({en_name})")

            else:

                new_source = VerifiedSource(
                    canonical_name=canonical_name,
                    display_name=config["name"],
                    aliases=config.get("aliases", []),
                    base_url=config["base_url"],
                    rss_url=config.get("rss_url"),
                    language="bn",
                    is_active=True,
                    body_selectors=config["body_selectors"],
                    title_selectors=config["title_selectors"],
                    date_selectors=config["date_selectors"],
                    internal_search_url=config["internal_search_url"],
                    article_url_patterns=config["article_url_patterns"],
                    description=f"Bangladeshi Bangla-language news outlet: {config.get('display_name_en', canonical_name)}",
                )
                session.add(new_source)
                created += 1
                en_name = config.get("display_name_en", canonical_name)
                print(f"  [CREATED] {canonical_name} ({en_name})")

        await session.commit()

    print()
    print(f"Done. Created: {created}, Updated: {updated}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(seed_verified_sources())
