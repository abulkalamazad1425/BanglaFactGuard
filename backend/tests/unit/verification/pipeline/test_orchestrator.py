"""Stage sequencing, reuse short-circuit and fault isolation, over fake stages."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.constants import PipelineStageID as S
from app.core.exceptions import PipelineError, StageError
from app.features.verification.pipeline.context import build_context
from app.features.verification.pipeline.orchestrator import PipelineOrchestrator


class Stage:
    def __init__(self, stage_id, log, *, fail: Exception | None = None, hit: bool = False):
        self.stage_id, self.log, self.fail, self.hit = stage_id, log, fail, hit

    async def execute(self, ctx):
        self.log.append(self.stage_id)
        if self.fail:
            raise self.fail
        ctx.cache_hit = ctx.cache_hit or self.hit
        return ctx


def run(stages, *, submission_id=None, repo=None):
    repo = repo or MagicMock(mark_processing=AsyncMock(), mark_failed=AsyncMock())
    ctx = build_context("h", "s", submission_id=submission_id)
    return PipelineOrchestrator(stages, repo), ctx, repo


async def test_every_stage_runs_in_order_and_is_timed():
    log = []
    orch, ctx, repo = run([Stage(sid, log) for sid in S], submission_id=uuid.uuid4())
    out = await orch.run(ctx)
    assert log == list(S) and set(out.stage_timings) == {s.value for s in S}
    repo.mark_processing.assert_awaited_once_with(ctx.submission_id)


async def test_a_reuse_hit_skips_everything_after_the_lookup():
    log = []
    stages = [Stage(S.S01_NORMALIZER, log), Stage(S.S02_CACHE_LOOKUP, log, hit=True),
              Stage(S.S03_QUERY_GENERATOR, log), Stage(S.S13_RESULT_PERSISTENCE, log)]
    orch, ctx, _ = run(stages)
    assert (await orch.run(ctx)).cache_hit and log == [S.S01_NORMALIZER, S.S02_CACHE_LOOKUP]


@pytest.mark.parametrize("error", [StageError(stage_id="s", message="search down"), RuntimeError("boom")])
async def test_a_non_critical_failure_is_recorded_and_the_run_continues(error):
    log = []
    orch, ctx, _ = run([Stage(S.S04_SOURCE_SEARCH, log, fail=error), Stage(S.S08_SOURCE_CORRESPONDENCE, log)])
    out = await orch.run(ctx)
    assert log == [S.S04_SOURCE_SEARCH, S.S08_SOURCE_CORRESPONDENCE]
    assert S.S04_SOURCE_SEARCH.value in out.stage_errors


@pytest.mark.parametrize("error", [StageError(stage_id="s", message="no source"), RuntimeError("boom")])
async def test_a_critical_failure_marks_the_submission_failed_and_stops(error):
    log = []
    orch, ctx, repo = run(
        [Stage(S.S01_NORMALIZER, log, fail=error), Stage(S.S02_CACHE_LOOKUP, log)], submission_id=uuid.uuid4()
    )
    with pytest.raises(PipelineError):
        await orch.run(ctx)
    assert log == [S.S01_NORMALIZER] and ctx.fatal_error
    repo.mark_failed.assert_awaited_once_with(ctx.submission_id)


async def test_status_bookkeeping_failures_never_mask_the_run():
    repo = MagicMock(mark_processing=AsyncMock(side_effect=RuntimeError("db")),
                     mark_failed=AsyncMock(side_effect=RuntimeError("db")))
    orch, ctx, _ = run([Stage(S.S01_NORMALIZER, [])], submission_id=uuid.uuid4(), repo=repo)
    await orch.run(ctx)  # mark_processing failing is only logged
    orch, ctx, _ = run([Stage(S.S12_RESULT_ASSEMBLY, [], fail=RuntimeError("x"))], submission_id=uuid.uuid4(), repo=repo)
    with pytest.raises(PipelineError):  # the original failure, not the bookkeeping one
        await orch.run(ctx)
    with pytest.raises(ValueError):
        PipelineOrchestrator([], repo)
