"""
Pipeline orchestrator - runs the verification stages in order over one
shared, observable, fault-tolerant `PipelineContext`.

## Responsibilities

1. **Stage sequencing**: S01 -> S02 -> ... -> S13, passing the context through.
2. **Reuse short-circuit**: if S02 sets `context.cache_hit`, every later
   stage is skipped; the service layer copies the reused automated result.
3. **Per-stage timing**: recorded in `context.stage_timings` (persisted with
   the result as `analysis_details.timings`).
4. **Non-fatal fault isolation**: a failing non-critical stage is recorded in
   `context.stage_errors` and the run continues with degraded data; the
   affected dimension then reports an explicit unavailable/incomplete state.
5. **Fatal error handling**: a failing CRITICAL stage marks the submission
   FAILED and raises `PipelineError` (the job retries or fails visibly).

## Stage criticality

| Stage | Critical? | On failure |
|-------|-----------|------------|
| S01 Normalizer | yes | no hash, no search |
| S02 Reuse lookup | no | run the full pipeline |
| S03 Query generator | no | no queries -> search INCOMPLETE |
| S04 Source search | no | failed calls -> source INCOMPLETE (never NOT_FOUND) |
| S05 Evidence retrieval | no | fetch failures -> source INCOMPLETE |
| S06 Article extractor | no | extraction failures -> source INCOMPLETE |
| S07 Evidence ranker | no | no ranked article |
| S08 Source correspondence | yes | the source decision every later stage depends on |
| S09 Headline alteration | no | no verdict; headline status MODEL_UNAVAILABLE |
| S10 Body similarity | no | body scores unavailable (never 0) |
| S11 Date verification | no | no date status |
| S12 Result assembly | yes | without it there is no coherent result |
| S13 Result persistence | yes | the result must be stored |
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

import structlog

from app.core.constants import PipelineStageID
from app.core.exceptions import PipelineError, StageError
from app.core.logging import bind_pipeline_context
from app.features.verification.pipeline.context import PipelineContext, PipelineStage

if TYPE_CHECKING:
    from app.features.submissions.repository import SubmissionRepository

logger = structlog.get_logger(__name__)


_CRITICAL_STAGES: frozenset[PipelineStageID] = frozenset(
    {
        PipelineStageID.S01_NORMALIZER,
        PipelineStageID.S08_SOURCE_CORRESPONDENCE,
        PipelineStageID.S12_RESULT_ASSEMBLY,
        PipelineStageID.S13_RESULT_PERSISTENCE,
    }
)


_POST_CACHE_STAGES: frozenset[PipelineStageID] = frozenset(
    {
        PipelineStageID.S03_QUERY_GENERATOR,
        PipelineStageID.S04_SOURCE_SEARCH,
        PipelineStageID.S05_EVIDENCE_RETRIEVAL,
        PipelineStageID.S06_ARTICLE_EXTRACTOR,
        PipelineStageID.S07_EVIDENCE_RANKER,
        PipelineStageID.S08_SOURCE_CORRESPONDENCE,
        PipelineStageID.S09_HEADLINE_ALTERATION,
        PipelineStageID.S10_BODY_SIMILARITY,
        PipelineStageID.S11_DATE_VERIFICATION,
        PipelineStageID.S12_RESULT_ASSEMBLY,
        PipelineStageID.S13_RESULT_PERSISTENCE,
    }
)


class PipelineOrchestrator:
    """Executes the verification stages (S01-S13) in sequence.

    Stages are injected (see `factory.build_verification_stages`), so tests
    can replace any of them without touching the orchestration logic.
    """

    def __init__(
        self,
        stages: list[PipelineStage],
        submission_repo: SubmissionRepository,
    ) -> None:
        if not stages:
            raise ValueError("PipelineOrchestrator requires at least one stage.")
        self.stages = stages
        self.submission_repo = submission_repo

    async def run(self, context: PipelineContext) -> PipelineContext:
        """Run every stage for one verification request. Raises
        `PipelineError` when a critical stage fails."""
        log = logger.bind(
            submission_id=str(context.submission_id) if context.submission_id else "pending",
            request_id=str(context.request_id),
        )

        log.info("pipeline_started", stage_count=len(self.stages))

        if context.submission_id:
            bind_pipeline_context(str(context.submission_id))
            try:
                await self.submission_repo.mark_processing(context.submission_id)
            except Exception as exc:

                log.warning("submission_status_update_failed", error=str(exc))

        for stage in self.stages:
            stage_id = stage.stage_id

            if context.cache_hit and stage_id in _POST_CACHE_STAGES:
                log.debug(
                    "stage_skipped_cache_hit",
                    stage=stage_id.value,
                )
                continue

            if context.has_fatal_error:
                log.warning(
                    "stage_skipped_fatal_error",
                    stage=stage_id.value,
                    fatal_error=context.fatal_error,
                )
                break

            stage_start = time.perf_counter()

            log.info("stage_started", stage=stage_id.value)

            try:
                context = await stage.execute(context)

                duration_ms = int((time.perf_counter() - stage_start) * 1000)
                context.record_stage_timing(stage_id, duration_ms)

                log.info(
                    "stage_completed",
                    stage=stage_id.value,
                    duration_ms=duration_ms,
                )

            except StageError as exc:
                duration_ms = int((time.perf_counter() - stage_start) * 1000)
                context.record_stage_timing(stage_id, duration_ms)

                if stage_id in _CRITICAL_STAGES:
                    context.fatal_error = str(exc.message)
                    log.error(
                        "critical_stage_failed",
                        stage=stage_id.value,
                        error=exc.message,
                        duration_ms=duration_ms,
                    )
                    await self._handle_fatal_failure(context)
                    raise PipelineError(
                        message=f"Critical stage {stage_id.value} failed: {exc.message}",
                        details={"stage": stage_id.value, "cause": exc.message},
                    ) from exc
                else:
                    context.record_stage_error(stage_id, exc.message)
                    log.warning(
                        "stage_failed_non_fatal",
                        stage=stage_id.value,
                        error=exc.message,
                        duration_ms=duration_ms,
                    )

            except Exception as exc:

                duration_ms = int((time.perf_counter() - stage_start) * 1000)
                context.record_stage_timing(stage_id, duration_ms)
                error_msg = f"{type(exc).__name__}: {exc!s}"

                if stage_id in _CRITICAL_STAGES:
                    context.fatal_error = error_msg
                    log.exception(
                        "critical_stage_unexpected_error",
                        stage=stage_id.value,
                        duration_ms=duration_ms,
                    )
                    await self._handle_fatal_failure(context)
                    raise PipelineError(
                        message=f"Unexpected error in critical stage {stage_id.value}",
                        details={"stage": stage_id.value, "cause": error_msg},
                    ) from exc
                else:
                    context.record_stage_error(stage_id, error_msg)
                    log.warning(
                        "stage_unexpected_error_non_fatal",
                        stage=stage_id.value,
                        error=error_msg,
                        duration_ms=duration_ms,
                    )

        total_ms = context.elapsed_ms
        log.info(
            "pipeline_completed",
            total_ms=total_ms,
            cache_hit=context.cache_hit,
            source_status=context.source_status.value if context.source_status else None,
            headline_verdict=context.content_status.value if context.content_status else None,
            headline_check_status=(
                context.headline_check_status.value if context.headline_check_status else None
            ),
            date_status=context.date_status.value if context.date_status else None,
            strength=context.confidence,
            stage_errors=context.stage_error_count,
        )

        return context

    async def _handle_fatal_failure(self, context: PipelineContext) -> None:
        """
        Mark the submission as FAILED in the database after a critical stage error.

        This is a best-effort operation — if the DB call itself fails, the
        exception is swallowed and only logged, because we are already
        in an error-handling path.

        Args:
            context: The pipeline context with `submission_id` set (may be None
                     if failure occurred in Stage 1 before DB insert).
        """
        if context.submission_id is None:
            return
        try:
            await self.submission_repo.mark_failed(context.submission_id)
            logger.error(
                "submission_marked_failed",
                submission_id=str(context.submission_id),
                fatal_error=context.fatal_error,
            )
        except Exception as exc:
            logger.error(
                "failed_to_mark_submission_failed",
                submission_id=str(context.submission_id),
                error=str(exc),
            )
