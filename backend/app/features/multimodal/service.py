"""
app/features/multimodal/service.py
====================================
Orchestrator for the multimodal fake-news prediction feature.

This service is the only entry point for business logic. It coordinates:
  1. Multimodal embedding extraction (text + image, concurrently).
  2. Duplicate detection by searching the DB for similar past predictions.
  3. Conditional model inference (skipped on cache hit).
  4. MinIO image upload (only for requests that proceed to inference).
  5. Persistence of the result with all embeddings.

## Cache-hit flow (duplicate detected)
    extract embeddings → search DB → found match →
    upload image → store dedup record (links to original) → return cached result

## Fresh inference flow (no duplicate)
    extract embeddings → search DB → no match →
    upload image → run model → store new record → return fresh result

Note: In both flows the image is uploaded to MinIO so every submission has a
stored copy regardless of whether it triggers inference. This makes the system
auditable: you can always retrieve the exact image submitted with any prediction.
"""

from __future__ import annotations

import uuid
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.features.multimodal.models import MultimodalPrediction
from app.features.multimodal.pipeline.embedding_extractor import MultimodalEmbeddingExtractor
from app.features.multimodal.pipeline.inference_engine import (
    MultimodalInferenceEngine,
    PredictionResult,
)
from app.features.multimodal.pipeline.model_loader import MultimodalModelLoader
from app.features.multimodal.repository import MultimodalPredictionRepository
from app.features.multimodal.schemas import MultimodalPredictionResponse
from app.features.multimodal.storage_service import MultimodalStorageService

logger = structlog.get_logger(__name__)
_SETTINGS = get_settings()


class MultimodalPredictionService:
    """
    Coordinates multimodal fake-news prediction with intelligent deduplication.

    Args:
        db:      Async SQLAlchemy session (per-request).
        loader:  Loaded model loader from ``app.state``.
        storage: MinIO storage service singleton.
    """

    def __init__(
        self,
        db: AsyncSession,
        loader: MultimodalModelLoader,
        storage: MultimodalStorageService,
    ) -> None:
        self._db = db
        self._loader = loader
        self._storage = storage
        self._repo = MultimodalPredictionRepository(db)
        self._extractor = MultimodalEmbeddingExtractor(loader)
        self._engine = MultimodalInferenceEngine(loader)
        self._cfg = _SETTINGS.multimodal

    # ------------------------------------------------------------------
    # Main predict method
    # ------------------------------------------------------------------

    async def predict(
        self,
        *,
        headline: str,
        body_text: str,
        image_bytes: bytes,
        original_filename: str,
    ) -> MultimodalPredictionResponse:
        """
        Process a multimodal fake-news prediction request.

        Args:
            headline:          News headline (stored for display, not passed to model).
            body_text:         Article body text (sole text input to BanglaBERT).
            image_bytes:       Raw image file bytes.
            original_filename: Original filename for MinIO key construction.

        Returns:
            ``MultimodalPredictionResponse`` with prediction and dedup metadata.
        """
        submission_id = str(uuid.uuid4())
        log = logger.bind(submission_id=submission_id)
        log.info("multimodal_predict_start", filename=original_filename)

        # ── Step 1: Extract all embeddings concurrently ────────────────
        text_emb, img_emb, combined_emb = await self._extractor.extract_all_embeddings(
            body_text=body_text,
            image_bytes=image_bytes,
        )
        log.debug("embeddings_extracted")

        # ── Step 2: Search for duplicate in DB ────────────────────────
        duplicate, similarity_scores = await self._find_duplicate(
            text_emb=text_emb,
            img_emb=img_emb,
            combined_emb=combined_emb,
        )

        # ── Step 3: Upload image to MinIO (always) ────────────────────
        minio_key = await self._storage.upload_image(
            image_bytes=image_bytes,
            original_filename=original_filename,
            submission_id=submission_id,
        )
        log.info("image_uploaded_to_minio", key=minio_key)

        # ── Step 4a: Cache hit — reuse existing prediction ─────────────
        if duplicate is not None:
            log.info(
                "multimodal_dedup_cache_hit",
                original_id=str(duplicate.id),
                **similarity_scores,
            )
            record = await self._repo.create(
                headline=headline,
                body_text=body_text,
                minio_object_key=minio_key,
                prediction=duplicate.prediction,
                confidence_fake=duplicate.confidence_fake,
                confidence_real=duplicate.confidence_real,
                text_embedding=text_emb,
                image_embedding=img_emb,
                combined_embedding=combined_emb,
                model_version=self._cfg.model_version,
                is_duplicate_of_id=duplicate.id,
            )
            return self._build_response(
                record=record,
                is_cached=True,
                original_id=str(duplicate.id),
                similarity_scores=similarity_scores,
            )

        # ── Step 4b: Fresh inference ────────────────────────────────────
        log.info("multimodal_running_fresh_inference")
        infer_result: PredictionResult = await self._engine.predict(
            body_text=body_text,
            image_bytes=image_bytes,
        )
        log.info(
            "multimodal_inference_done",
            prediction=infer_result.prediction,
            confidence_fake=round(infer_result.confidence_fake, 4),
        )

        record = await self._repo.create(
            headline=headline,
            body_text=body_text,
            minio_object_key=minio_key,
            prediction=infer_result.prediction,
            confidence_fake=infer_result.confidence_fake,
            confidence_real=infer_result.confidence_real,
            text_embedding=text_emb,
            image_embedding=img_emb,
            combined_embedding=combined_emb,
            model_version=self._cfg.model_version,
            is_duplicate_of_id=None,
        )
        return self._build_response(record=record, is_cached=False)

    # ------------------------------------------------------------------
    # Retrieve stored prediction
    # ------------------------------------------------------------------

    async def get_prediction(self, prediction_id: uuid.UUID) -> MultimodalPrediction:
        """Retrieve a prediction by ID (raises RecordNotFoundError if missing)."""
        return await self._repo.get_by_id(prediction_id)

    async def list_predictions(
        self, *, limit: int = 20, offset: int = 0
    ) -> tuple[list[MultimodalPrediction], int]:
        """Return paginated recent predictions and total count."""
        records = await self._repo.list_recent(limit=limit, offset=offset)
        return list(records), len(records)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _find_duplicate(
        self,
        *,
        text_emb,
        img_emb,
        combined_emb,
    ) -> tuple[MultimodalPrediction | None, dict[str, float]]:
        """
        Query the DB for similar past predictions and apply the three-level
        multimodal similarity check.

        Returns:
            (matching_record_or_None, best_similarity_scores_dict)
        """
        candidates = await self._repo.find_similar_candidates(
            model_version=self._cfg.model_version,
        )

        best_match: MultimodalPrediction | None = None
        best_scores: dict[str, float] = {}

        for candidate in candidates:
            import numpy as np
            cand_text_emb = np.array(candidate.text_embedding, dtype=np.float32)
            cand_img_emb = np.array(candidate.image_embedding, dtype=np.float32)
            cand_combined_emb = np.array(candidate.combined_embedding, dtype=np.float32)

            is_dup, scores = self._extractor.is_duplicate(
                query_text_emb=text_emb,
                query_img_emb=img_emb,
                query_combined_emb=combined_emb,
                candidate_text_emb=cand_text_emb,
                candidate_img_emb=cand_img_emb,
                candidate_combined_emb=cand_combined_emb,
            )

            if is_dup:
                best_match = candidate
                best_scores = scores
                break  # candidates are ordered by recency; first match wins

        return best_match, best_scores

    @staticmethod
    def _build_response(
        *,
        record: MultimodalPrediction,
        is_cached: bool,
        original_id: str | None = None,
        similarity_scores: dict[str, float] | None = None,
    ) -> MultimodalPredictionResponse:
        return MultimodalPredictionResponse(
            prediction_id=str(record.id),
            prediction=record.prediction,
            confidence_fake=record.confidence_fake,
            confidence_real=record.confidence_real,
            is_cached=is_cached,
            original_id=original_id,
            similarity_scores=similarity_scores if is_cached else None,
            minio_object_key=record.minio_object_key,
            model_version=record.model_version,
            created_at=record.created_at,
        )
