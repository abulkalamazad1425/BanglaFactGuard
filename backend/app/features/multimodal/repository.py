from __future__ import annotations

import uuid
from typing import Sequence

import numpy as np
import structlog
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.constants import MultimodalPredictionLabel
from app.core.exceptions import RecordNotFoundError
from app.features.multimodal.models import MultimodalAnalysis, MultimodalPrediction

logger = structlog.get_logger(__name__)
_SETTINGS = get_settings()


class MultimodalPredictionRepository:
    """Legacy — frozen. Nothing calls this after the PDF-schema cutover; kept so
    the pre-cutover multimodal_predictions rows stay queryable if ever needed."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

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


class MultimodalAnalysisRepository:
    """Live storage for the /multimodal/predict endpoint (DatabaseDescription.pdf
    Table 4.9), replacing MultimodalPredictionRepository above."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(
        self,
        *,
        submission_id: uuid.UUID,
        image_object_key: str,
        prediction: str,
        confidence_fake: float,
        confidence_real: float,
        text_embedding: np.ndarray,
        image_embedding: np.ndarray,
        combined_embedding: np.ndarray,
        model_version: str,
        is_duplicate_of_id: uuid.UUID | None = None,
    ) -> MultimodalAnalysis:
        record = MultimodalAnalysis(
            submission_id=submission_id,
            image_object_key=image_object_key,
            prediction=MultimodalPredictionLabel(prediction),
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
            "multimodal_analysis_created",
            analysis_id=str(record.id),
            submission_id=str(submission_id),
            prediction=prediction,
            is_duplicate=is_duplicate_of_id is not None,
        )
        return record

    async def get_by_id(self, analysis_id: uuid.UUID) -> MultimodalAnalysis:
        result = await self._db.execute(
            select(MultimodalAnalysis).where(MultimodalAnalysis.id == analysis_id)
        )
        record = result.scalar_one_or_none()
        if record is None:
            raise RecordNotFoundError(
                model="MultimodalAnalysis",
                identifier=str(analysis_id),
            )
        return record

    async def get_by_submission_id(
        self, submission_id: uuid.UUID
    ) -> MultimodalAnalysis | None:
        result = await self._db.execute(
            select(MultimodalAnalysis).where(
                MultimodalAnalysis.submission_id == submission_id
            )
        )
        return result.scalar_one_or_none()

    async def list_recent(
        self, *, limit: int = 20, offset: int = 0
    ) -> Sequence[MultimodalAnalysis]:
        result = await self._db.execute(
            select(MultimodalAnalysis)
            .order_by(desc(MultimodalAnalysis.created_at))
            .limit(limit)
            .offset(offset)
        )
        return result.scalars().all()

    async def find_similar_candidates(
        self,
        *,
        model_version: str,
        limit: int | None = None,
    ) -> Sequence[MultimodalAnalysis]:
        n = limit or _SETTINGS.multimodal.dedup_candidate_limit
        result = await self._db.execute(
            select(MultimodalAnalysis)
            .where(MultimodalAnalysis.model_version == model_version)
            .order_by(desc(MultimodalAnalysis.created_at))
            .limit(n)
        )
        rows = result.scalars().all()
        logger.debug(
            "dedup_candidates_fetched",
            count=len(rows),
            model_version=model_version,
        )
        return rows
