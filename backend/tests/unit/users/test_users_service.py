"""My Submissions (owner only, filters before pagination, the same display
rules as the result page), statistics and the profile's live total."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from app.core.constants import (
    ContentStatus,
    HeadlineAlterationStatus,
    MultimodalPredictionLabel,
    OverallVerdict,
    SourceStatus,
    SubmissionStatus,
    SubmissionType,
)
from app.features.submissions.models import PhotocardExtraction
from app.features.users.service import UserAccountService
from tests.helpers.db import add_completed_submission, add_multimodal_submission, add_user


async def mine(session, user, headline, status, *, kind=SubmissionType.SOURCE_BASED, duplicate_of=None, **fields):
    sub, res = await add_completed_submission(session, headline=headline, submitter_id=user.id, submission_type=kind, **fields)
    sub.status, sub.duplicate_of_submission_id = status, duplicate_of
    await session.flush()
    return sub, res


async def test_my_submissions_are_private_and_filtered_before_paging(session):
    me, other = await add_user(session), await add_user(session)
    final, _ = await mine(session, me, "ঢাকায় মেট্রোরেল চালু", SubmissionStatus.FINALIZED)
    review, _ = await mine(session, me, "বন্যায় ক্ষতিগ্রস্ত কৃষক", SubmissionStatus.EXPERT_REVIEW)
    running, _ = await mine(session, me, "ঢাকায় বাস ভাড়া বাড়ল", SubmissionStatus.PROCESSING, kind=SubmissionType.PHOTO_CARD)
    failed, _ = await mine(session, me, "নির্বাচন কমিশনের বৈঠক", SubmissionStatus.FAILED)
    # a re-submitted copy of a finalized claim: stored EXPERT_REVIEW, shown (and filtered) as final
    dup, _ = await mine(session, me, "ঢাকায় মেট্রোরেল চালু", SubmissionStatus.EXPERT_REVIEW, duplicate_of=final.id)
    await mine(session, other, "ঢাকায় অন্য কারও দাবি", SubmissionStatus.FINALIZED)
    svc = UserAccountService(session)

    async def ids(**kw):
        return {r.submission_id for r in await svc.my_submissions(me, limit=50, offset=0, **kw)}

    assert await ids() == {str(s.id) for s in (final, review, running, failed, dup)}
    assert await ids(state="final") == {str(final.id), str(dup.id)}
    assert await ids(state="review") == {str(review.id)}
    assert await ids(state="in_progress") == {str(running.id)}
    assert await ids(state="failed") == {str(failed.id)}
    assert await ids(submission_type=SubmissionType.PHOTO_CARD) == {str(running.id)}
    assert await ids(q="ঢাকায়") == {str(final.id), str(running.id), str(dup.id)}  # never another user's
    assert await ids(q="ঢাকায়", state="in_progress") == {str(running.id)}
    assert len(await svc.my_submissions(me, limit=2, offset=0)) == 2


async def test_each_row_shows_ai_findings_and_only_a_final_decision(session):
    me = await add_user(session)
    finalized, _ = await mine(session, me, "চূড়ান্ত", SubmissionStatus.FINALIZED, overall_verdict=OverallVerdict.FAKE,
                              content_status=ContentStatus.ALTERED)
    open_, _ = await mine(session, me, "চলমান", SubmissionStatus.EXPERT_REVIEW, headline_exact_match=True)
    legacy, _ = await mine(session, me, "পুরনো", SubmissionStatus.EXPERT_REVIEW, headline_check_status=None)
    mm, analysis = await add_multimodal_submission(session, submitter_id=me.id, prediction=MultimodalPredictionLabel.NON_FAKE)
    card, _ = await mine(session, me, "কার্ড", SubmissionStatus.EXPERT_REVIEW, kind=SubmissionType.PHOTO_CARD)
    session.add(PhotocardExtraction(submission_id=card.id, image_object_key="photocard/k.png", status="SUCCEEDED"))
    await session.flush()
    storage = MagicMock(get_presigned_url=AsyncMock(return_value="https://img/k.png"))
    rows = {r.submission_id: r for r in await UserAccountService(session, photocard_storage=storage).my_submissions(me, limit=10, offset=0)}

    f = rows[str(finalized.id)]
    assert (f.is_finalized, f.overall_verdict, f.headline_status) == (True, OverallVerdict.FAKE, HeadlineAlterationStatus.ALTERED)
    o = rows[str(open_.id)]
    assert (o.is_finalized, o.overall_verdict, o.headline_status) == (False, None, HeadlineAlterationStatus.EXACT_MATCHED)
    assert rows[str(legacy.id)].content_status is None  # an old content verdict is not a headline verdict
    m = rows[str(mm.id)]
    assert (m.prediction, m.is_finalized, m.overall_verdict) == (MultimodalPredictionLabel.NON_FAKE, False, None)
    assert rows[str(card.id)].image_url == "https://img/k.png"
    analysis.expert_overall_verdict = OverallVerdict.REAL
    await session.flush()
    rows = {r.submission_id: r for r in await UserAccountService(session).my_submissions(me, limit=10, offset=0)}
    assert (rows[str(mm.id)].is_finalized, rows[str(mm.id)].overall_verdict) == (True, OverallVerdict.REAL)


async def test_statistics_and_the_profile_total_are_counted_live(session):
    me = await add_user(session, total_submissions=1)  # the drifted cached counter
    await mine(session, me, "এক", SubmissionStatus.EXPERT_REVIEW)
    await mine(session, me, "দুই", SubmissionStatus.EXPERT_REVIEW, content_status=ContentStatus.ALTERED)
    await mine(session, me, "তিন", SubmissionStatus.EXPERT_REVIEW, source_status=SourceStatus.NOT_FOUND)
    await mine(session, me, "চার", SubmissionStatus.PENDING, kind=SubmissionType.PHOTO_CARD)
    svc = UserAccountService(session)
    stats = await svc.my_submission_stats(me)
    assert (stats.total, stats.pending, stats.source_confirmed, stats.source_not_found,
            stats.content_matched, stats.content_altered) == (4, 1, 3, 1, 2, 1)
    assert (await svc.profile(me)).total_submissions == 4
    profile = await svc.update_full_name(me, "নতুন নাম")
    assert profile.full_name == "নতুন নাম" and (await svc.update_full_name(me, None)).full_name == "নতুন নাম"
