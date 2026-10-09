"""S02: reuse an identical, complete, current result. The database row is
authoritative; a Redis pointer is only a hint that is re-validated."""

from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import delete

from app.core.config import get_settings
from app.core.constants import VERIFICATION_PIPELINE_VERSION, SourceStatus
from app.features.submissions.models import Submission
from app.features.submissions.repository import SubmissionRepository
from app.features.verification.pipeline.stages.s02_cache_lookup import CacheLookupStage
from app.features.verification.repository import ResultRepository
from tests.helpers.db import add_completed_submission
from tests.helpers.pipeline import make_context

HEADLINE = "সরকার নতুন সেতু উদ্বোধন করেছে"


def cache(pointer=None, *, raw: bytes | None = None, error: bool = False) -> MagicMock:
    c = MagicMock(set_claim_pointer=AsyncMock(), invalidate_claim=AsyncMock())
    value = raw if raw is not None else (json.dumps(pointer).encode() if pointer else None)
    c.get_claim_result = AsyncMock(side_effect=RuntimeError("redis down") if error else None, return_value=value)
    return c


def pointer(sub) -> dict:
    return {"submission_id": str(sub.id), "pipeline_version": VERIFICATION_PIPELINE_VERSION}


async def lookup(session, sub, c, *, own_id=None):
    ctx = make_context(HEADLINE)
    ctx.content_hash, ctx.submission_id = sub.content_hash, own_id
    return await CacheLookupStage(c, SubmissionRepository(session), ResultRepository(session)).execute(ctx)


async def test_a_complete_result_is_reused_from_the_database_and_written_back(session):
    sub, _ = await add_completed_submission(session, headline=HEADLINE, submitter_id=None)
    c = cache()
    out = await lookup(session, sub, c)
    assert out.cache_hit and out.reused_from_submission_id == sub.id and out.source_status == SourceStatus.CONFIRMED
    written = json.loads(c.set_claim_pointer.await_args.args[1])
    assert written["submission_id"] == str(sub.id) and c.set_claim_pointer.await_args.kwargs["ttl"] == (
        get_settings().redis.ttl_claim_result
    )


@pytest.mark.parametrize("redis", ["valid", "malformed", "down"])
async def test_redis_pointer_hits_and_falls_back_to_the_database(session, redis):
    sub, _ = await add_completed_submission(session, headline=HEADLINE, submitter_id=None)
    c = {"valid": cache(pointer(sub)), "malformed": cache(raw=b"{not json"), "down": cache(error=True)}[redis]
    out = await lookup(session, sub, c)
    assert out.cache_hit and out.reused_from_submission_id == sub.id
    assert c.set_claim_pointer.await_count == (0 if redis == "valid" else 1)  # DB hits are written back


@pytest.mark.parametrize("fields", [
    dict(source_status=SourceStatus.INCOMPLETE),
    dict(pipeline_version="v-old"),
    dict(content_status=None, headline_check_status="UNDETERMINED"),
    dict(content_status=None, headline_check_status="MODEL_UNAVAILABLE"),
    dict(analysis_details={"reused_from_submission_id": str(uuid.uuid4())}),  # a copy is never a source
])
async def test_a_result_that_is_not_a_settled_answer_is_never_reused(session, fields):
    sub, result = await add_completed_submission(session, headline=HEADLINE, submitter_id=None, **fields)
    if "content_status" in fields:
        result.content_status = None
    for c in (cache(), cache(pointer(sub))):
        assert (await lookup(session, sub, c)).cache_hit is False


async def test_a_pointer_to_a_deleted_or_own_submission_is_never_served(session):
    sub, _ = await add_completed_submission(session, headline=HEADLINE, submitter_id=None)
    assert (await lookup(session, sub, cache(pointer(sub)), own_id=sub.id)).cache_hit is False  # itself
    await session.execute(delete(Submission).where(Submission.id == sub.id))
    c = cache(pointer(sub))
    out = await lookup(session, sub, c)
    assert out.cache_hit is False and out.reused_from_submission_id is None
    c.invalidate_claim.assert_awaited_once()


async def test_without_an_identity_nothing_is_looked_up(session):
    c = cache()
    ctx = make_context(HEADLINE)
    ctx.content_hash = None
    assert (await CacheLookupStage(c, SubmissionRepository(session), ResultRepository(session)).execute(ctx)).cache_hit is False
    c.get_claim_result.assert_not_awaited()


async def test_not_found_pointers_expire_sooner():
    c = cache()
    await CacheLookupStage.write_pointer(c, "h", uuid.uuid4(), SourceStatus.NOT_FOUND)
    assert c.set_claim_pointer.await_args.kwargs["ttl"] == get_settings().redis.ttl_not_found_result
