"""Stored predictions: duplicate candidates come only from the same model
version, newest first, bounded."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

from app.core.exceptions import RecordNotFoundError
from app.features.multimodal.repository import MultimodalAnalysisRepository
from tests.helpers.db import add_multimodal_submission, store_vectors_as_json


async def test_candidates_are_same_version_newest_first(session, monkeypatch):
    store_vectors_as_json(monkeypatch)
    repo = MultimodalAnalysisRepository(session)
    vec = np.ones(3, dtype=np.float32)
    created = []
    for n, version in enumerate(("v1", "v1", "v2")):
        sub, seeded = await add_multimodal_submission(session, headline=f"h{n}")
        await session.delete(seeded)  # store our own analysis instead
        await session.flush()
        row = await repo.create(submission_id=sub.id, image_object_key=f"k{n}", prediction="FAKE", confidence_fake=0.7,
                                confidence_real=0.3, text_embedding=vec, image_embedding=vec, combined_embedding=vec,
                                model_version=version)
        row.created_at = datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=n)
        created.append(row)
    await session.flush()
    assert [r.id for r in await repo.find_similar_candidates(model_version="v1")] == [created[1].id, created[0].id]
    assert len(await repo.find_similar_candidates(model_version="v1", limit=1)) == 1
    assert created[0].text_embedding == [1.0, 1.0, 1.0]
    assert [r.id for r in await repo.list_recent(limit=1)] == [created[2].id] and await repo.count_all() == 3
    with pytest.raises(RecordNotFoundError):
        await repo.get_by_id(uuid.uuid4())
