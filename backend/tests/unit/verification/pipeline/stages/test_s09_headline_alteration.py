"""S09: claim headline vs the selected source TITLE. The source body can
never change the verdict, and a missing comparison is never a verdict."""

from __future__ import annotations

from app.core.constants import ContentStatus, HeadlineCheckStatus, PipelineStageID, SourceStatus
from app.features.verification import source_policy
from app.features.verification.analysis.headline_comparison import HeadlineComparator
from app.features.verification.pipeline.stages.s09_headline_alteration import (
    HeadlineAlterationStage,
)
from tests.helpers.pipeline import ENTAILS, FakeEmbedder, FakeNLI, article, make_context

HEADLINE = "বাংলাদেশ ব্যাংক নীতি সুদহার বাড়াল"
TITLE = "নীতি সুদহার বাড়িয়েছে বাংলাদেশ ব্যাংক"
BODY = "বাংলাদেশ ব্যাংক আজ নীতি সুদহার বাড়িয়েছে। মূল্যস্ফীতি নিয়ন্ত্রণে এই সিদ্ধান্ত।"


def confirmed(headline=HEADLINE, title=TITLE, body=BODY):
    ctx = make_context(headline, top=article(title, body))
    ctx.source_status = SourceStatus.CONFIRMED
    return ctx


async def compare(ctx, nli=None):
    nli = nli or FakeNLI({(TITLE, HEADLINE): ENTAILS})
    return await HeadlineAlterationStage(HeadlineComparator(nli, FakeEmbedder())).execute(ctx)


async def test_the_verdict_comes_from_the_title_alone_and_is_fully_explained():
    verdicts = set()
    for body in (BODY, "সম্পূর্ণ ভিন্ন একটি প্রতিবেদন যেখানে সুদহার কমানোর কথা বলা হয়েছে।", None):
        nli = FakeNLI({(TITLE, HEADLINE): ENTAILS})
        ctx = await compare(confirmed(body=body), nli)
        verdicts.add((ctx.content_status, ctx.headline_check_status))
        assert all(BODY not in p and BODY not in h for p, h in nli.calls)
    assert verdicts == {(ContentStatus.MATCHED, HeadlineCheckStatus.COMPLETED)}
    detail = ctx.analysis.headline_alteration
    assert (detail.claim_headline, detail.source_title, detail.source_url, detail.source_publisher) == (
        HEADLINE, TITLE, "https://prothomalo.com/article/1", "prothomalo.com",
    )
    assert detail.basis == "semantic_equivalence" and detail.semantic.available


async def test_an_altered_headline_carries_its_quoted_differences():
    ctx = await compare(confirmed("সড়ক দুর্ঘটনায় ১০ জন নিহত", "সড়ক দুর্ঘটনায় ৫ জন নিহত"))
    assert ctx.content_status == ContentStatus.ALTERED
    assert ctx.analysis.headline_alteration.differences[0].kind == "numbers"


async def test_no_source_and_an_incomplete_search_are_different_non_verdicts():
    not_found = make_context(HEADLINE)
    not_found.source_status = SourceStatus.NOT_FOUND
    out = await compare(not_found)
    assert (out.content_status, out.headline_check_status) == (None, HeadlineCheckStatus.SOURCE_NOT_FOUND)
    assert "claimed source" in out.analysis.headline_alteration.reason
    not_found.verification_mode = source_policy.VERIFIED_SOURCES
    assert "verified sources" in (await compare(not_found)).analysis.headline_alteration.reason

    incomplete = make_context(HEADLINE)
    incomplete.source_status = SourceStatus.INCOMPLETE
    out = await compare(incomplete)
    assert out.headline_check_status == HeadlineCheckStatus.SOURCE_CHECK_INCOMPLETE
    assert "not a finding" in out.analysis.headline_alteration.reason


async def test_an_untitled_article_or_a_crashed_comparison_gives_no_verdict():
    out = await compare(confirmed(title=None))
    assert (out.content_status, out.headline_check_status) == (None, HeadlineCheckStatus.SOURCE_TITLE_MISSING)
    assert out.stage_errors[PipelineStageID.S09_HEADLINE_ALTERATION.value]

    class Crashing:
        async def compare(self, *args):
            raise RuntimeError("model crashed")

    out = await HeadlineAlterationStage(Crashing()).execute(confirmed())
    assert (out.content_status, out.headline_check_status) == (None, HeadlineCheckStatus.MODEL_UNAVAILABLE)
