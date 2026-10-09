"""Fact Explorer search (keyword ranking, filters, pagination after ranking)
and the guarded status transitions."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone

import pytest

from app.core.constants import (
    ContentStatus,
    MultimodalPredictionLabel,
    OverallVerdict,
    SubmissionStatus,
    SubmissionType,
)
from app.core.exceptions import RecordNotFoundError
from app.features.submissions.repository import SubmissionRepository
from tests.helpers.db import add_completed_submission, add_multimodal_submission


@pytest.fixture
async def ranked(session):
    base = datetime(2026, 10, 1, tzinfo=timezone.utc)
    rows = {}
    # newest first by created_at, so ranking (not date) must decide the order
    for i, (key, headline, body) in enumerate([
        ("one", "ঢাকায় নতুন সেতু", None),
        ("two", "বাস দুর্ঘটনায় আহত ১০", "ঢাকা শহরে"),
        ("three_scattered", "দুর্ঘটনা: ঢাকা থেকে ছাড়া বাস উল্টে", None),
        ("three_phrase", "ঢাকা বাস দুর্ঘটনা নিয়ে তদন্ত", None),
        ("none", "নির্বাচন কমিশনের বৈঠক", None),
        ("pct", "দাম বেড়েছে 50% পর্যন্ত", None),
    ]):
        sub, _ = await add_completed_submission(session, headline=headline, body=body, submitter_id=None)
        sub.created_at = base + timedelta(hours=10 - i)
        rows[key] = sub
    await session.flush()
    return SubmissionRepository(session), rows


async def test_keyword_search_ranks_by_distinct_keywords_before_paginating(ranked):
    repo, rows = ranked
    order = [rows[k].id for k in ("three_phrase", "three_scattered", "two", "one")]  # exact phrase wins the tie
    found, total = await repo.search(keyword="ঢাকা বাস দুর্ঘটনা")
    assert total == 4 and [r.id for r in found] == order
    page1, t1 = await repo.search(keyword="ঢাকা বাস দুর্ঘটনা", limit=2, offset=0)
    page2, t2 = await repo.search(keyword="ঢাকা বাস দুর্ঘটনা", limit=2, offset=2)
    assert t1 == t2 == 4 and [r.id for r in page1 + page2] == order
    found, total = await repo.search(keyword="   ")
    assert total == 6 and found[0].id == rows["one"].id  # no query: newest first


async def test_keyword_search_is_literal_and_nukta_insensitive(ranked):
    repo, rows = ranked
    found, total = await repo.search(keyword="50%")
    assert total == 1 and found[0].id == rows["pct"].id
    assert (await repo.search(keyword="%"))[1] == 1  # a wildcard is just a character
    precomposed, _ = await add_completed_submission(repo.session, headline="রিকনসিলিয়েশন ছাড়া", submitter_id=None)
    split, _ = await add_completed_submission(repo.session, headline="নিরাপত্তা বায়ুসেনা মোতায়েন", submitter_id=None)
    for query, expected in (("রিকনসিলিয়েশন", precomposed), ("মোতায়েন", split)):
        found, total = await repo.search(keyword=query)
        assert total == 1 and found[0].id == expected.id


async def test_archive_scope_counts_and_review_filters(session):
    final, _ = await add_completed_submission(session, headline="Final", submitter_id=None, overall_verdict=OverallVerdict.REAL)
    review, _ = await add_completed_submission(session, headline="Review", submitter_id=None)
    escalated, _ = await add_completed_submission(session, headline="Escalated", submitter_id=None)
    escalated.status = SubmissionStatus.ESCALATED
    duplicate, _ = await add_completed_submission(session, headline="Repeat", submitter_id=None)
    duplicate.duplicate_of_submission_id = review.id
    failed, _ = await add_completed_submission(session, headline="Failed", submitter_id=None)
    failed.status = SubmissionStatus.FAILED
    mm, _ = await add_multimodal_submission(session, prediction=MultimodalPredictionLabel.NON_FAKE)
    await session.flush()
    repo = SubmissionRepository(session)

    assert await repo.explorer_summary() == {"total": 4, "finalized": 1, "review": 3}
    rows, total = await repo.search(review_state="finalized")
    assert total == 1 and rows[0].id == final.id
    rows, total = await repo.search(review_state="review")
    assert {r.id for r in rows} == {review.id, escalated.id, mm.id}
    assert (await repo.search(overall_verdict=OverallVerdict.REAL))[1] == 1  # a NON_FAKE prediction is never final
    assert (await repo.search(method=SubmissionType.MULTIMODAL))[1] == 1


async def test_finding_and_date_filters_use_the_ai_call_and_whole_days(session):
    sub, _ = await add_completed_submission(session, headline="Corrected", submitter_id=None,
                                            content_status=ContentStatus.MATCHED, final_content_status=ContentStatus.ALTERED)
    sub.created_at = datetime(2026, 10, 2, 23, 59, tzinfo=timezone.utc)
    later, _ = await add_completed_submission(session, headline="Tomorrow", submitter_id=None)
    later.created_at = datetime(2026, 10, 3, 0, 0, tzinfo=timezone.utc)
    await session.flush()
    repo = SubmissionRepository(session)
    day = dict(date_from=date(2026, 10, 2), date_to=date(2026, 10, 2))
    rows, total = await repo.search(**day, content_status=ContentStatus.MATCHED)
    assert total == 1 and rows[0].id == sub.id
    assert (await repo.search(**day, content_status=ContentStatus.ALTERED))[1] == 0  # supplementary value ignored


async def test_status_transitions_happen_once(session):
    sub, _ = await add_completed_submission(session, headline="h", submitter_id=None)
    repo = SubmissionRepository(session)
    assert await repo.escalate_if_open(sub.id) is True and await repo.escalate_if_open(sub.id) is False
    await session.refresh(sub)
    assert sub.status == SubmissionStatus.ESCALATED and sub.escalated_at
    assert await repo.mark_failed(sub.id) is False  # an escalated claim cannot fail

    other, _ = await add_completed_submission(session, headline="h2", submitter_id=None)
    other.status = SubmissionStatus.PROCESSING
    await session.flush()
    assert await repo.mark_failed(other.id, "bad") is True and await repo.mark_failed(other.id) is False
    await session.refresh(other)
    assert (other.status, other.failure_reason, other.processing_phase) == (SubmissionStatus.FAILED, "bad", "FAILED")
    await repo.mark_ai_done(other.id)
    await session.refresh(other)
    assert (other.status, other.failure_reason) == (SubmissionStatus.EXPERT_REVIEW, None)
    with pytest.raises(RecordNotFoundError):
        await repo.get_by_id_locked(uuid.uuid4())
