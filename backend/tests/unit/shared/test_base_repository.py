import uuid

import pytest

from app.core.exceptions import DuplicateRecordError, RecordNotFoundError
from app.features.sources.models import VerifiedSource
from app.features.verification.models import VerificationResult
from app.shared.base_repository import BaseRepository, rows_by_submission
from tests.helpers.db import add_completed_submission


class Sources(BaseRepository[VerifiedSource]):
    model_class = VerifiedSource


def source(name: str) -> VerifiedSource:
    return VerifiedSource(canonical_name=name, display_name=name, base_url=f"https://{name}", is_active=True)


async def test_crud_round_trip(session):
    repo = Sources(session)
    created = await repo.create(source("a.com"))
    assert await repo.bulk_create([]) == []
    await repo.bulk_create([source("b.com"), source("c.com")])
    assert await repo.count() == 3
    assert [s.canonical_name for s in await repo.list_all(limit=2, order_by=VerifiedSource.canonical_name)] == [
        "a.com", "b.com",
    ]
    updated = await repo.update(created, display_name="A")
    assert (await repo.get_by_id(created.id)).display_name == updated.display_name == "A"
    with pytest.raises(AttributeError):
        await repo.update(created, no_such_field=1)
    await repo.delete_by_id(created.id)
    assert await repo.get_by_id_or_none(created.id) is None
    with pytest.raises(RecordNotFoundError):
        await repo.get_by_id(uuid.uuid4())


async def test_unique_violation_is_a_duplicate_record_error(session):
    repo = Sources(session)
    await repo.create(source("a.com"))
    with pytest.raises(DuplicateRecordError):
        await repo.create(source("a.com"))


async def test_rows_by_submission_maps_one_row_per_submission(session):
    sub, result = await add_completed_submission(session, headline="h", submitter_id=None)
    assert await rows_by_submission(session, VerificationResult, [sub.id, uuid.uuid4()]) == {sub.id: result}
    assert await rows_by_submission(session, VerificationResult, []) == {}
