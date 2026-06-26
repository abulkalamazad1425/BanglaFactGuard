"""
app/features/multimodal/repository.py
======================================
Database access layer for multimodal predictions.

All queries use the async SQLAlchemy 2.0 API. The session is injected via
FastAPI's dependency injection system (``get_async_session``).

Duplicate detection search strategy:
    The ``find_similar_candidates`` method fetches the most recent N predictions
    (configurable via ``MULTIMODAL_DEDUP_CANDIDATE_LIMIT``) for the same
    model version and returns them. The caller (MultimodalPredictionService)
    then computes exact cosine similarity on all three embedding dimensions to
    identify genuine duplicates.

    This avoids requiring pgvector (a PostgreSQL extension) while still being
    efficient enough for typical traffic volumes. For large-scale deployments,
    replace the ``ORDER BY created_at DESC LIMIT N`` scan with a pgvector
    HNSW index query.
"""

from __future__ import annotations

import uuid
from typing import Sequence

import numpy as np
import structlog
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import RecordNotFoundError
from app.features.multimodal.models import MultimodalPrediction

logger = structlog.get_logger(__name__)
_SETTINGS = get_settings()


class MultimodalPredictionRepository:
    """
    CRUD and search operations for ``MultimodalPrediction`` records.

    Args:
        db: An async SQLAlchemy session (injected via FastAPI DI).
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    async def create(
        self,
        *,
        headline: str,
        body_text: str,
        minio_object_key: str,
        prediction: str,
        confidence_fake: float,
        confidence_real: float,
        text_embedding: np.ndarray,
        image_embedding: np.ndarray,
        combined_embedding: np.ndarray,
        model_version: str,
        is_duplicate_of_id: uuid.UUID | None = None,
    ) -> MultimodalPrediction:
        """
        Persist a new prediction record and return it.

        Embeddings are stored as plain Python lists (PostgreSQL ARRAY(Float)).
        """
        record = MultimodalPrediction(
            headline=headline,
            body_text=body_text,
            minio_object_key=minio_object_key,
            prediction=prediction,
            confidence_fake=confidence_fake,
            confidence_real=confidence_real,
            text_embedding=text_embedding.tolist(),
            image_embedding=image_embedding.tolist(),
            combined_embedding=combined_embedding.tolist(),
            model_version=model_version,
            is_duplicate_of_id=is_duplicate_of_id,
        )
        self._db.add(record)
        await self._db.flush()   # populate id / timestamps without committing
        await self._db.refresh(record)
        logger.info(
            "multimodal_prediction_created",
            prediction_id=str(record.id),
            prediction=prediction,
            is_duplicate=is_duplicate_of_id is not None,
        )
        return record

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    async def get_by_id(self, prediction_id: uuid.UUID) -> MultimodalPrediction:
        """
        Retrieve a single prediction by primary key.

        Raises:
            RecordNotFoundError: If no record with the given id exists.
        """
        result = await self._db.execute(
            select(MultimodalPrediction).where(MultimodalPrediction.id == prediction_id)
        )
        record = result.scalar_one_or_none()
        if record is None:
            raise RecordNotFoundError(
                model="MultimodalPrediction",
                identifier=str(prediction_id),
            )
        return record

    async def list_recent(self, *, limit: int = 20, offset: int = 0) -> Sequence[MultimodalPrediction]:
        """Return the most recent predictions ordered by creation time (desc)."""
        result = await self._db.execute(
            select(MultimodalPrediction)
            .order_by(desc(MultimodalPrediction.created_at))
            .limit(limit)
            .offset(offset)
        )
        return result.scalars().all()

    # ------------------------------------------------------------------
    # Duplicate detection — candidate retrieval
    # ------------------------------------------------------------------

    async def find_similar_candidates(
        self,
        *,
        model_version: str,
        limit: int | None = None,
    ) -> Sequence[MultimodalPrediction]:
        """
        Fetch recent predictions for the same model version to use as
        duplicate-detection candidates.

        Returns the N most recent rows (default: ``MULTIMODAL_DEDUP_CANDIDATE_LIMIT``).
        The caller is responsible for computing cosine similarities and
        deciding whether any candidate is a genuine duplicate.

        Args:
            model_version: Only candidates of the same model version are returned;
                           this prevents stale model results from being reused.
            limit:         Override the default candidate limit from settings.
        """
        n = limit or _SETTINGS.multimodal.dedup_candidate_limit
        result = await self._db.execute(
            select(MultimodalPrediction)
            .where(MultimodalPrediction.model_version == model_version)
            .order_by(desc(MultimodalPrediction.created_at))
            .limit(n)
        )
        rows = result.scalars().all()
        logger.debug(
            "dedup_candidates_fetched",
            count=len(rows),
            model_version=model_version,
        )
        return rows
