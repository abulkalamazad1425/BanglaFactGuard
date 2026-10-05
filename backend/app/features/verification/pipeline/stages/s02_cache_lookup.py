from __future__ import annotations

import json
import uuid

import structlog

from app.core.constants import (
    VERIFICATION_PIPELINE_VERSION,
    PipelineStageID,
    SourceStatus,
)
from app.features.cache.cache_service import CacheService
from app.features.submissions.repository import SubmissionRepository
from app.features.verification.pipeline.context import PipelineContext
from app.features.verification.repository import ResultRepository
from app.features.verification.reuse import ResultReuseService, result_is_reusable

logger = structlog.get_logger(__name__)


class CacheLookupStage:
    """Looks for an earlier, identical, complete, FRESH verification.

    Identity is `context.content_hash` (headline, body-if-scoped, canonical
    source, claimed date, scope, pipeline version — see
    `hashing.compute_claim_hash`). Redis holds only a *pointer* to the
    submission that produced the last complete result; the database row is
    authoritative and is re-validated (current pipeline version, no incomplete
    dimension or missing headline verdict, freshness — shorter for NOT_FOUND)
    on every hit, so stale or
    incompatible cached scores can never overlay a stored result. The same
    freshness rules apply to the database fallback as to Redis.

    A hit never repoints `context.submission_id`: the caller's own submission
    (owner, photo-card image, OCR record) stays the target and the service
    layer copies the automated result onto it (`ResultReuseService`).
    `force_refresh` bypasses both paths.
    """

    stage_id = PipelineStageID.S02_CACHE_LOOKUP

    def __init__(
        self,
        cache_service: CacheService,
        submission_repo: SubmissionRepository,
        result_repo: ResultRepository,
    ) -> None:
        self.cache_service = cache_service
        self.submission_repo = submission_repo
        self.result_repo = result_repo
        self.reuse = ResultReuseService(submission_repo, result_repo)

    async def execute(self, context: PipelineContext) -> PipelineContext:
        log = logger.bind(stage=self.stage_id.value, content_hash=context.content_hash)

        context.cache_hit = False
        if context.force_refresh:
            log.info("cache_bypassed_force_refresh")
            return context
        if not context.content_hash:
            log.warning("content_hash_missing_skipping_cache")
            return context

        try:
            if await self._check_redis(context, log):
                return context
        except Exception as exc:
            log.warning("redis_cache_error", error=str(exc))

        try:
            if await self._check_db(context, log):
                return context
        except Exception as exc:
            log.warning("db_cache_error", error=str(exc))

        log.info("cache_miss")
        return context

    async def _check_redis(self, context: PipelineContext, log) -> bool:
        raw = await self.cache_service.get_claim_result(context.content_hash)
        if raw is None:
            log.debug("redis_miss")
            return False
        try:
            pointer = json.loads(raw)
            submission_id = uuid.UUID(pointer["submission_id"])
        except (json.JSONDecodeError, KeyError, ValueError, TypeError) as exc:
            log.warning("redis_cache_deserialisation_error", error=str(exc))
            return False
        if pointer.get("pipeline_version") != VERIFICATION_PIPELINE_VERSION:
            log.info("redis_pointer_version_mismatch")
            return False

        result = await self.result_repo.get_by_submission_id(submission_id)
        ok, reason = result_is_reusable(result)
        if not ok:
            log.info("redis_pointer_rejected", reason=reason)
            await self.cache_service.invalidate_claim(context.content_hash)
            return False
        self._populate(context, submission_id, result)
        log.info("redis_hit", submission_id=str(submission_id))
        return True

    async def _check_db(self, context: PipelineContext, log) -> bool:
        found = await self.reuse.find_reusable(
            context.content_hash, exclude_submission_id=context.submission_id
        )
        if found is None:
            log.debug("db_miss")
            return False
        submission, result = found
        self._populate(context, submission.id, result)
        log.info("db_hit", submission_id=str(submission.id))
        try:
            await self.write_pointer(
                self.cache_service, context.content_hash, submission.id, result.source_status
            )
        except Exception as exc:
            log.warning("redis_write_back_failed", error=str(exc))
        return True

    @staticmethod
    def _populate(context: PipelineContext, source_submission_id: uuid.UUID, result) -> None:
        """Mark the hit. The reused automated result itself is copied by the
        service layer (`ResultReuseService.materialize`); nothing of it is
        replayed into this context."""
        context.cache_hit = True
        context.reused_from_submission_id = source_submission_id
        context.source_status = SourceStatus(result.source_status)

    @staticmethod
    async def write_pointer(
        cache_service: CacheService,
        content_hash: str,
        submission_id: uuid.UUID,
        source_status: SourceStatus | None,
    ) -> None:
        """Record the submission holding the latest complete result for this
        identity. TTL is the shorter NOT_FOUND window when applicable."""
        from app.core.config import get_settings

        redis = get_settings().redis
        ttl = redis.ttl_not_found_result if source_status == SourceStatus.NOT_FOUND else redis.ttl_claim_result
        await cache_service.set_claim_pointer(
            content_hash,
            json.dumps(
                {
                    "submission_id": str(submission_id),
                    "pipeline_version": VERIFICATION_PIPELINE_VERSION,
                    "source_status": source_status.value if source_status else None,
                },
                ensure_ascii=False,
            ),
            ttl=ttl,
        )
