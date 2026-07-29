"""
app/pipelines/orchestrator.py
==============================
Pipeline Orchestrator — wires all 12 stages into a single, observable,
fault-tolerant verification run.

## Responsibilities

1. **Stage sequencing**: Execute S01 → S02 → … → S12 in order, passing
   the shared `PipelineContext` through each stage.

2. **Cache short-circuit**: If Stage 2 sets `context.cache_hit = True`,
   the orchestrator skips Stages 3–12 and returns immediately.

3. **Per-stage timing**: Each stage is timed; results are stored in
   `context.stage_timings` and written to `verification_logs` in Stage 12.

4. **Non-fatal fault isolation**: Each stage executes inside a try/except.
   A `StageError` (or any unexpected exception from a non-critical stage)
   records the error in `context.stage_errors` and allows the pipeline to
   continue with degraded data. This trades completeness for resilience —
   e.g. if the NER stage fails, similarity analysis still runs with empty
   entities.

5. **Fatal error handling**: Some stages are marked CRITICAL (S01, S02,
   S11, S12). If a critical stage raises, the orchestrator sets
   `context.fatal_error`, marks the claim as FAILED, and re-raises.

6. **Structured logging**: Every stage start/end/error is logged with
   `claim_id`, `stage_id`, and timing — providing full observability
   without any application-level profiling tooling.

## Stage criticality

| Stage | Critical? | Reason |
|-------|-----------|--------|
| S01 Normalizer | ✅ | Without normalisation, no hash, no search |
| S02 Cache Lookup | ❌ | Cache failure = continue to full pipeline |
| S03 Query Generator | ❌ | Degrade to single headline query |
| S04 Source Search | ❌ | Zero results → NOT_FOUND verdict |
| S05 Evidence Retrieval | ❌ | Zero fetched → NOT_FOUND verdict |
| S06 Article Extractor | ❌ | Zero extracted → NOT_FOUND verdict |
| S07 Evidence Ranker | ❌ | Fallback: use raw extraction order |
| S08 Similarity Analyzer | ❌ | Degrade: scores remain None |
| S09 Contradiction Detector | ❌ | Degrade: contradiction_score = None |
| S10 Manipulation Detector | ❌ | Degrade: all flags = False |
| S11 Classifier | ✅ | Without a label, no result |
| S12 Persistence | ✅ | Result must be stored |
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

import structlog

from app.core.constants import ClaimStatus, PipelineStageID
from app.core.exceptions import PipelineError, StageError
from app.core.logging import bind_pipeline_context
from app.features.verification.pipeline.context import PipelineContext, PipelineStage

if TYPE_CHECKING:
    from app.features.verification.repository import ClaimRepository

logger = structlog.get_logger(__name__)


_CRITICAL_STAGES: frozenset[PipelineStageID] = frozenset(
    {
        PipelineStageID.S01_NORMALIZER,
        PipelineStageID.S11_CLASSIFIER,
        PipelineStageID.S12_PERSISTENCE,
    }
)


_POST_CACHE_STAGES: frozenset[PipelineStageID] = frozenset(
    {
        PipelineStageID.S03_QUERY_GENERATOR,
        PipelineStageID.S04_SOURCE_SEARCH,
        PipelineStageID.S05_EVIDENCE_RETRIEVAL,
        PipelineStageID.S06_ARTICLE_EXTRACTOR,
        PipelineStageID.S07_EVIDENCE_RANKER,
        PipelineStageID.S08_SIMILARITY_ANALYZER,
        PipelineStageID.S09_CONTRADICTION_DETECTOR,
        PipelineStageID.S10_MANIPULATION_DETECTOR,
        PipelineStageID.S11_CLASSIFIER,
        PipelineStageID.S12_PERSISTENCE,
    }
)


class PipelineOrchestrator:
    """
    Executes all 12 verification pipeline stages in sequence.

    Each stage is a `PipelineStage`-conforming object injected at construction
    time by `VerificationService`. This makes the orchestrator fully testable —
    individual stages can be replaced with mocks in unit tests without
    touching the orchestration logic.

    Attributes:
        stages: Ordered list of PipelineStage implementations (S01–S12).
        claim_repo: ClaimRepository for status lifecycle management.
    """

    def __init__(
        self,
        stages: list[PipelineStage],
        claim_repo: ClaimRepository,
    ) -> None:
        """
        Initialise the orchestrator with an ordered list of stages.

        Args:
            stages:     Ordered list of S01–S12 stage implementations.
            claim_repo: Repository used to update claim status during the run.
        """
        if not stages:
            raise ValueError("PipelineOrchestrator requires at least one stage.")
        self.stages = stages
        self.claim_repo = claim_repo

    async def run(self, context: PipelineContext) -> PipelineContext:
        """
        Execute the full 12-stage pipeline for a single verification request.

        This is the only public method on the orchestrator. It is called by
        `VerificationService.verify()` after the initial DB record is created.

        Pipeline flow:
          S01 → S02 ─→ (cache hit?) ──YES──► return
                       │ NO
                       ▼
               S03 → S04 → S05 → S06 → S07 → S08 → S09 → S10 → S11 → S12
                                                                    ▲
                  Each stage failure (non-critical) is logged ──────┘
                  and the pipeline continues with degraded data.

        Args:
            context: Fully initialised PipelineContext with input fields set.

        Returns:
            The same PipelineContext object with all stage outputs populated.

        Raises:
            PipelineError: If a CRITICAL stage fails (S01, S11, or S12).
        """
        log = logger.bind(
            claim_id=str(context.claim_id) if context.claim_id else "pending",
            request_id=str(context.request_id),
        )

        log.info("pipeline_started", stage_count=len(self.stages))

        if context.claim_id:
            bind_pipeline_context(str(context.claim_id))
            try:
                await self.claim_repo.mark_processing(context.claim_id)
            except Exception as exc:

                log.warning("claim_status_update_failed", error=str(exc))

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
            label=context.label.value if context.label else None,
            confidence=context.confidence,
            stage_errors=context.stage_error_count,
        )

        return context

    async def _handle_fatal_failure(self, context: PipelineContext) -> None:
        """
        Mark the claim as FAILED in the database after a critical stage error.

        This is a best-effort operation — if the DB call itself fails, the
        exception is swallowed and only logged, because we are already
        in an error-handling path.

        Args:
            context: The pipeline context with `claim_id` set (may be None
                     if failure occurred in Stage 1 before DB insert).
        """
        if context.claim_id is None:
            return
        try:
            await self.claim_repo.mark_failed(context.claim_id)
            logger.error(
                "claim_marked_failed",
                claim_id=str(context.claim_id),
                fatal_error=context.fatal_error,
            )
        except Exception as exc:
            logger.error(
                "failed_to_mark_claim_failed",
                claim_id=str(context.claim_id),
                error=str(exc),
            )
