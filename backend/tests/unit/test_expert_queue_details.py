"""Expert queue details expose the Headline Alteration detail and body scores
from the saved result, after a full persist -> reload round trip."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from app.core.constants import ClaimScope, ContentStatus, HeadlineCheckStatus
from app.features.expert_review.models import ExpertReview
from app.features.expert_review.repository import ExpertReviewRepository
from app.features.expert_review.service import ExpertReviewService
from app.features.submissions.repository import RetrievedArticleRepository, SubmissionRepository
from app.features.verification.pipeline.stages.s13_result_persistence import ResultPersistenceStage
from app.features.verification.repository import ResultRepository
from app.shared.models_registry import Base
from app.shared.utils.hashing import compute_claim_hash
from db_helpers import add_source, add_user, make_session_factory
from pipeline_helpers import article, make_context, run_analysis

HEADLINE = "সড়ক দুর্ঘটনায় ১০ জন নিহত"
TITLE = "সড়ক দুর্ঘটনায় ৫ জন নিহত"
BODY = "সড়ক দুর্ঘটনায় পাঁচজন নিহত হয়েছেন। আহত হয়েছেন আরও দশজন।"


async def test_expert_queue_item_shows_headline_detail_and_body_scores_after_reload():
    engine, factory = await make_session_factory()
    async with engine.begin() as conn:
        await conn.run_sync(lambda c: Base.metadata.create_all(c, tables=[ExpertReview.__table__]))
    async with factory() as s:
        await add_source(s)
        user = await add_user(s)
        ctx = make_context(HEADLINE, body=BODY, top=article(TITLE, BODY))
        ctx.submitter_id = user.id
        ctx.content_hash = compute_claim_hash(HEADLINE, "prothomalo.com", ClaimScope.HEADLINE_WITH_BODY, body=BODY)
        ctx = await run_analysis(ctx)
        cache = MagicMock(set_claim_pointer=AsyncMock())
        ctx = await ResultPersistenceStage(
            SubmissionRepository(s), ResultRepository(s), RetrievedArticleRepository(s), cache, session=s
        ).execute(ctx)
        await s.commit()
        submission_id = ctx.submission_id

    async with factory() as s:
        service = ExpertReviewService(
            ExpertReviewRepository(s), MagicMock(), MagicMock(), SubmissionRepository(s), ResultRepository(s),
            MagicMock(), MagicMock(),
        )
        item = await service.get_queue_item(submission_id)
    await engine.dispose()

    assert item.content_status == ContentStatus.ALTERED
    assert item.headline_check_status == HeadlineCheckStatus.COMPLETED
    assert item.ai_label == "Source: CONFIRMED · Headline: ALTERED"
    ha = item.headline_alteration
    assert ha.claim_headline == HEADLINE and ha.source_title == TITLE
    assert ha.source_url == "https://prothomalo.com/article/1" and ha.source_publisher == "prothomalo.com"
    assert ha.exact_match is False and ha.differences and ha.differences[0].kind == "numbers"
    body = item.body_similarity
    assert body.status.value == "COMPUTED"
    assert body.jaccard.available and body.tfidf_cosine.available and body.normalized_levenshtein.available
