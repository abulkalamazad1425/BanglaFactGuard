"""Verification work is reusable; a submission is not. Only a settled,
current, original result is reused - copied onto the requester's own row."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.core.constants import (
    VERIFICATION_PIPELINE_VERSION,
    DateStatus,
    SourceStatus,
    SubmissionStatus,
)
from app.features.submissions.repository import SubmissionRepository
from app.features.verification.repository import ResultRepository
from app.features.verification.reuse import REUSED_FROM_KEY, ResultReuseService, result_is_reusable
from tests.helpers.db import add_completed_submission


@pytest.mark.parametrize("fields,reason", [
    (dict(), "reusable"),
    (dict(source_status=SourceStatus.NOT_FOUND), "reusable"),
    (dict(pipeline_version=None), "pipeline_version_mismatch"),
    (dict(source_status=SourceStatus.INCOMPLETE), "incomplete_check"),
    (dict(date_status=DateStatus.INCOMPLETE), "incomplete_check"),
    (dict(headline_check_status="UNDETERMINED"), "no_headline_verdict"),
    (dict(body="বডি", body_comparison_status="UNAVAILABLE"), "body_scores_unavailable"),
    (dict(analysis_details={REUSED_FROM_KEY: str(uuid.uuid4())}), "copied_result"),
])
async def test_reusability_rules(session, fields, reason):
    _, result = await add_completed_submission(session, headline="h", submitter_id=None, **fields)
    if reason == "no_headline_verdict":
        result.content_status = None
    result.created_at = datetime.now(timezone.utc) - timedelta(days=400)  # there is no age limit
    assert result_is_reusable(result) == (reason == "reusable", reason)
    assert result_is_reusable(None) == (False, "no_result")


async def test_the_newest_reusable_original_is_found_and_copied_once(session):
    service = ResultReuseService(SubmissionRepository(session), ResultRepository(session))
    stale, _ = await add_completed_submission(session, headline="h", submitter_id=None, pipeline_version="v-old")
    source, source_result = await add_completed_submission(session, headline="h", submitter_id=None)
    source_result.analysis_details = {"timings": {"stage_ms": {"s04": 1}}, "metrics": {}}
    assert stale.content_hash == source.content_hash
    found = await service.find_reusable(source.content_hash)
    assert found == (source, source_result)
    assert await service.find_reusable(source.content_hash, exclude_submission_id=source.id) is None

    target, target_result = await add_completed_submission(session, headline="h2", submitter_id=None)
    await session.delete(target_result)
    target.status = SubmissionStatus.PROCESSING
    await session.flush()
    copy = await service.materialize(source=source, source_result=source_result, target=target)
    assert copy.reused_from_submission_id == source.id and copy.pipeline_version == VERIFICATION_PIPELINE_VERSION
    assert "timings" not in copy.analysis_details and copy.analysis_details[REUSED_FROM_KEY] == str(source.id)
    assert (target.duplicate_of_submission_id, target.status, target.processing_phase) == (
        source.id, SubmissionStatus.EXPERT_REVIEW, "DONE",
    )
    assert await service.materialize(source=source, source_result=source_result, target=target) is copy
