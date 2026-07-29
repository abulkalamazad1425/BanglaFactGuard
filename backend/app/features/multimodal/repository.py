
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

    def __init__(self, db: AsyncSession) -> None:
        self._db = db





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
        await self._db.flush()
        await self._db.refresh(record)
        logger.info(
            "multimodal_prediction_created",
            prediction_id=str(record.id),
            prediction=prediction,
            is_duplicate=is_duplicate_of_id is not None,
        )
        return record





    async def get_by_id(self, prediction_id: uuid.UUID) -> MultimodalPrediction:
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
        result = await self._db.execute(
            select(MultimodalPrediction)
            .order_by(desc(MultimodalPrediction.created_at))
            .limit(limit)
            .offset(offset)
        )
        return result.scalars().all()





    async def find_similar_candidates(
        self,
        *,
        model_version: str,
        limit: int | None = None,
    ) -> Sequence[MultimodalPrediction]:
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
