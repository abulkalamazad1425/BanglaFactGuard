"""Verified-source management: create/update/delete, active-only listing and
keyword search with a matching total."""

import pytest

from app.core.exceptions import DuplicateRecordError, RecordNotFoundError
from app.features.sources.repository import SourceRepository
from app.features.sources.schemas import SourceCreateSchema, SourceUpdateSchema
from app.features.sources.service import SourceService
from tests.helpers.db import add_source


async def test_lifecycle_and_duplicate_protection(session):
    svc = SourceService(SourceRepository(session))
    created = await svc.create_source(SourceCreateSchema(
        canonical_name="samakal.com", display_name="সমকাল", base_url="https://samakal.com", aliases=["সমকাল"],
    ))
    assert created.is_active and (await svc.get_source(created.id)).display_name == "সমকাল"
    with pytest.raises(DuplicateRecordError):
        await svc.create_source(SourceCreateSchema(canonical_name="samakal.com", display_name="x", base_url="https://samakal.com"))
    updated = await svc.update_source(created.id, SourceUpdateSchema(display_name="দৈনিক সমকাল"))
    assert updated.display_name == "দৈনিক সমকাল"
    assert (await svc.update_source(created.id, SourceUpdateSchema())).display_name == "দৈনিক সমকাল"
    await svc.delete_source(created.id)
    with pytest.raises(RecordNotFoundError):
        await svc.get_source(created.id)


async def test_listing_and_search_respect_activity_and_report_matching_totals(session):
    await add_source(session, "prothomalo.com")
    star = await add_source(session, "bangla.thedailystar.net", display_name="দ্য ডেইলি স্টার", aliases=["daily star"])
    await add_source(session, "jugantor.com", display_name="যুগান্তর", is_active=False)
    svc = SourceService(SourceRepository(session))

    active = await svc.list_sources(size=2)
    assert (active.total, active.pages) == (2, 1)
    every = await svc.list_sources(include_inactive=True, size=2)
    assert (every.total, every.pages, len(every.items)) == (3, 2, 2)
    assert (await svc.list_sources(include_inactive=True, size=2, page=2)).items[0].canonical_name == "prothomalo.com"

    for q in ("ডেইলি", "daily star"):  # Bangla name or alias
        res = await svc.list_sources(include_inactive=True, q=q)
        assert res.total == 1 and res.items[0].id == star.id
    assert (await svc.list_sources(include_inactive=True, q="যুগান্তর")).total == 1
    assert (await svc.list_sources(include_inactive=False, q="যুগান্তর")).total == 0
    assert (await svc.list_sources(include_inactive=True, q="zzqq")).total == 0
