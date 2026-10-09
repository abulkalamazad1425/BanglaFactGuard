"""GET /multimodal/predictions: `total` is the number of stored analyses,
not the size of the requested page."""

import uuid
from unittest.mock import MagicMock

import pytest
from sqlalchemy import ARRAY
from sqlalchemy.ext.compiler import compiles

from app.core.constants import MultimodalPredictionLabel, SubmissionType
from app.features.multimodal.models import MultimodalAnalysis
from app.features.multimodal.service import MultimodalPredictionService
from tests.unit.db_helpers import add_completed_submission, make_session_factory


@compiles(ARRAY, "sqlite")
def _array_sqlite(type_, compiler, **kw):  # pragma: no cover - trivial shim
    return "JSON"


@pytest.mark.asyncio
async def test_total_counts_all_rows_not_the_page():
    engine, factory = await make_session_factory()
    try:
        async with engine.begin() as conn:
            await conn.run_sync(lambda c: MultimodalAnalysis.__table__.create(c))
        async with factory() as session:
            for n in range(3):
                sub, _ = await add_completed_submission(
                    session, headline=f"h{n}", submitter_id=None,
                    submission_type=SubmissionType.MULTIMODAL,
                )
                session.add(MultimodalAnalysis(
                    id=uuid.uuid4(), submission_id=sub.id, image_object_key=f"k{n}",
                    prediction=MultimodalPredictionLabel.FAKE, confidence_fake=0.7,
                    confidence_real=0.3, model_version="test",
                ))
            await session.flush()

            service = MultimodalPredictionService(db=session, loader=MagicMock(), storage=MagicMock())
            records, total = await service.list_predictions(limit=2, offset=0)

        assert len(records) == 2
        assert total == 3
    finally:
        await engine.dispose()
