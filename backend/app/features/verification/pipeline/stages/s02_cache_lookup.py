from __future__ import annotations

import json

import structlog

from app.core.constants import PipelineStageID, VerificationLabel
from app.features.verification.pipeline.context import PipelineContext
from app.features.verification.repository import ClaimRepository
from app.features.verification.repository import ResultRepository
from app.features.articles.schemas import RankedArticleSchema
from app.features.verification.schemas import (
    ManipulationFlagsSchema,
    VerificationScoresSchema,
)
from app.features.cache.cache_service import CacheService

logger = structlog.get_logger(__name__)


class CacheLookupStage:

    stage_id = PipelineStageID.S02_CACHE_LOOKUP

    def __init__(
        self,
        cache_service: CacheService,
        claim_repo: ClaimRepository,
        result_repo: ResultRepository,
    ) -> None:

        self.cache_service = cache_service
        self.claim_repo = claim_repo
        self.result_repo = result_repo

    async def execute(self, context: PipelineContext) -> PipelineContext:

        log = logger.bind(
            stage=self.stage_id.value,
            claim_hash=context.claim_hash,
        )

        if context.force_refresh:
            log.info("cache_bypassed_force_refresh")
            context.cache_hit = False
            return context

        if not context.claim_hash:
            log.warning("claim_hash_missing_skipping_cache")
            context.cache_hit = False
            return context

        try:
            redis_hit = await self._check_redis(context, log)
            if redis_hit:
                return context
        except Exception as exc:
            log.warning("redis_cache_error", error=str(exc))

        try:
            db_hit = await self._check_db(context, log)
            if db_hit:
                return context
        except Exception as exc:
            log.warning("db_cache_error", error=str(exc))

        log.info("cache_miss")
        context.cache_hit = False
        return context

    async def _check_redis(
        self,
        context: PipelineContext,
        log: structlog.BoundLogger,
    ) -> bool:

        cached_bytes = await self.cache_service.get_claim_result(context.claim_hash)

        if cached_bytes is None:
            log.debug("redis_miss")
            return False

        try:
            cached_data: dict = json.loads(cached_bytes)
            self._populate_context_from_cache(context, cached_data)
            log.info("redis_hit", label=context.cached_label)
            return True
        except (json.JSONDecodeError, KeyError, ValueError) as exc:
            log.warning("redis_cache_deserialisation_error", error=str(exc))

            return False

    async def _check_db(
        self,
        context: PipelineContext,
        log: structlog.BoundLogger,
    ) -> bool:

        claim = await self.claim_repo.get_completed_by_hash(context.claim_hash)
        if claim is None:
            log.debug("db_miss")
            return False

        result = await self.result_repo.get_by_claim_id(claim.id)
        if result is None:
            log.debug("db_claim_found_but_no_result", claim_id=str(claim.id))
            return False

        context.claim_id = claim.id
        context.normalized_source = claim.normalized_source
        context.cached_label = VerificationLabel(result.label)
        context.cached_confidence = result.confidence
        context.cached_reasoning = result.reasoning or ""
        context.cached_scores = VerificationScoresSchema(
            semantic_similarity=result.semantic_similarity,
            entity_match=result.entity_match,
            contradiction_score=result.contradiction_score,
            keyword_overlap=result.keyword_overlap,
            numerical_consistency=result.numerical_consistency,
        )
        context.cached_manipulation_flags = ManipulationFlagsSchema()
        context.cache_hit = True

        log.info(
            "db_hit",
            claim_id=str(claim.id),
            label=context.cached_label.value,
        )

        try:
            await self._write_to_redis(context)
        except Exception as exc:
            log.warning("redis_write_back_failed", error=str(exc))

        return True

    def _populate_context_from_cache(
        self, context: PipelineContext, data: dict
    ) -> None:

        context.cache_hit = True
        context.cached_label = VerificationLabel(data["label"])
        context.cached_confidence = float(data["confidence"])
        context.cached_reasoning = data.get("reasoning", "")
        context.cached_scores = VerificationScoresSchema(**data.get("scores", {}))
        context.cached_manipulation_flags = ManipulationFlagsSchema(
            **data.get("manipulation_flags", {})
        )

        raw_articles = data.get("matched_articles", [])
        context.cached_matched_articles = [
            RankedArticleSchema(**a) for a in raw_articles
        ]
        if data.get("claim_id"):
            import uuid as _uuid

            context.claim_id = _uuid.UUID(data["claim_id"])
        if data.get("normalized_source"):
            context.normalized_source = data["normalized_source"]

    async def _write_to_redis(self, context: PipelineContext) -> None:

        payload = {
            "label": context.cached_label.value if context.cached_label else None,
            "confidence": context.cached_confidence,
            "reasoning": context.cached_reasoning,
            "scores": (
                context.cached_scores.model_dump() if context.cached_scores else {}
            ),
            "manipulation_flags": (
                context.cached_manipulation_flags.model_dump()
                if context.cached_manipulation_flags
                else {}
            ),
            "matched_articles": [
                a.model_dump(mode="json") for a in context.cached_matched_articles
            ],
            "claim_id": str(context.claim_id) if context.claim_id else None,
            "normalized_source": context.normalized_source,
        }
        await self.cache_service.set_claim_result(
            context.claim_hash,
            json.dumps(payload, ensure_ascii=False),
        )
