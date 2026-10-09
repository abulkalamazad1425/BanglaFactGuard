"""Registry lookups by canonical name and the active/all listings. (The alias
lookup uses Postgres JSONB containment and cannot run on SQLite.)"""

from app.features.sources.repository import SourceRepository
from tests.helpers.db import add_source


async def test_canonical_lookup_and_listings(session):
    await add_source(session, "prothomalo.com", language="bn")
    await add_source(session, "thedailystar.net", language="en")
    await add_source(session, "jugantor.com", is_active=False)
    repo = SourceRepository(session)
    assert (await repo.get_by_canonical_name("  ProthomAlo.com ")).canonical_name == "prothomalo.com"
    assert (await repo.resolve_source("PROTHOMALO.COM")).canonical_name == "prothomalo.com"
    assert [s.canonical_name for s in await repo.list_active()] == ["prothomalo.com", "thedailystar.net"]
    assert [s.canonical_name for s in await repo.list_active(language="EN")] == ["thedailystar.net"]
    assert [s.canonical_name for s in await repo.list_all(language="bn")] == ["jugantor.com", "prothomalo.com"]
    assert (await repo.count_active(), await repo.count_all()) == (2, 3)
    items, total = await repo.search("jugantor", include_inactive=False)
    assert (items, total) == ([], 0)
