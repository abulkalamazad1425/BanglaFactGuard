"""
scripts/seed_verified_sources.py
=================================
One-time seeding script to upsert all entries from the source registry into
the verified_sources database table.

## Usage

Run from the backend directory:

    python -m scripts.seed_verified_sources

Or with explicit connection:

    python scripts/seed_verified_sources.py

## What it does

For each source in SOURCE_REGISTRY:
  - Checks if a VerifiedSource with that canonical_name already exists.
  - If it exists: updates only the scraping fields (selectors, patterns, URLs)
    and display_name — does NOT overwrite is_active or custom aliases added later.
  - If it does NOT exist: creates a full new record.

This is idempotent — safe to run multiple times.
"""

from __future__ import annotations

import asyncio
import sys
import os

# Add backend root to path so we can import app modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Import ALL ORM model modules so SQLAlchemy can fully resolve every
# relationship before any mapper configuration is triggered.
import app.features.sources.models  # noqa: F401, E402
import app.features.verification.models  # noqa: F401, E402
import app.features.articles.models  # noqa: F401, E402

from sqlalchemy import select  # noqa: E402
from app.db.engine import AsyncSessionLocal  # noqa: E402
from app.features.sources.models import VerifiedSource  # noqa: E402
from app.features.verification.pipeline.source_registry import SOURCE_REGISTRY  # noqa: E402


async def seed_verified_sources() -> None:
    """Upsert all SOURCE_REGISTRY entries into the verified_sources table."""
    print("=" * 60)
    print("Seeding verified_sources table from SOURCE_REGISTRY...")
    print("=" * 60)

    async with AsyncSessionLocal() as session:
        created = 0
        updated = 0

        for canonical_name, config in SOURCE_REGISTRY.items():
            # Check if already exists
            result = await session.execute(
                select(VerifiedSource).where(
                    VerifiedSource.canonical_name == canonical_name
                )
            )
            existing = result.scalar_one_or_none()

            if existing:
                # Update scraping config fields only
                existing.display_name = config["name"]
                existing.body_selectors = config["body_selectors"]
                existing.title_selectors = config["title_selectors"]
                existing.date_selectors = config["date_selectors"]
                existing.internal_search_url = config["internal_search_url"]
                existing.article_url_patterns = config["article_url_patterns"]
                existing.base_url = config["base_url"]

                # Merge aliases (don't remove custom aliases added later)
                current_aliases: list[str] = existing.aliases or []
                registry_aliases: list[str] = config.get("aliases", [])
                merged = list(set(current_aliases) | set(registry_aliases))
                existing.aliases = merged

                # RSS URL (update if None)
                if existing.rss_url is None and config.get("rss_url"):
                    existing.rss_url = config["rss_url"]

                session.add(existing)
                updated += 1
                en_name = config.get('display_name_en', canonical_name)
                print(f"  [UPDATED] {canonical_name} ({en_name})")

            else:
                # Create new record
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
                en_name = config.get('display_name_en', canonical_name)
                print(f"  [CREATED] {canonical_name} ({en_name})")

        await session.commit()

    print()
    print(f"Done. Created: {created}, Updated: {updated}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(seed_verified_sources())
