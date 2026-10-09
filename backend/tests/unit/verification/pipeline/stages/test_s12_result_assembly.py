"""S12: one explainable result with the dimensions kept separate, and never
an automated overall (Fake/Real) verdict."""

from __future__ import annotations

from datetime import date

import pytest

from app.core.constants import (
    VERIFICATION_PIPELINE_VERSION,
    ClaimScope,
    HeadlineCheckStatus,
    SourceStatus,
)
from app.core.exceptions import ClassificationError
from app.features.verification import source_policy
from app.features.verification.pipeline.stages.s12_result_assembly import ResultAssemblyStage
from tests.helpers.pipeline import ENTAILS, FakeNLI, article, make_context, run_analysis

HEADLINE = "বাংলাদেশ ব্যাংক নীতি সুদহার বাড়াল"
TITLE = "নীতি সুদহার বাড়িয়েছে বাংলাদেশ ব্যাংক"
BODY = "বাংলাদেশ ব্যাংক আজ নীতি সুদহার বাড়িয়েছে। মূল্যস্ফীতি নিয়ন্ত্রণে এই সিদ্ধান্ত।"
NLI = {(TITLE, HEADLINE): ENTAILS}


PADMA = ("পদ্মা সেতু দিয়ে যান চলাচল শুরু", "উদ্বোধনের পরদিন পদ্মা সেতু দিয়ে যান চলাচল শুরু")


@pytest.mark.parametrize("headline,title,claimed,published,phrases", [
    (HEADLINE, TITLE, date(2026, 6, 7), date(2026, 6, 7), ["Headline Alteration: matched", "date matches"]),
    (HEADLINE, TITLE, date(2026, 1, 1), date(2026, 6, 7), ["Headline Alteration: matched", "differs from the report's"]),
    (HEADLINE, TITLE, date(2026, 6, 7), None, ["could not be determined"]),
    (HEADLINE, TITLE, None, date(2026, 6, 7), ["No publication date was claimed"]),
    ("বাংলাদেশ ব্যাংক নীতি সুদহার কমাল ৫ শতাংশ", TITLE, None, None, ["Headline Alteration: altered"]),
    (*PADMA, None, None, ["Headline Alteration: no verdict"]),
])
async def test_confirmed_source_reasoning_explains_each_dimension(headline, title, claimed, published, phrases):
    ctx = make_context(headline, body=BODY, published_date=claimed, top=article(title, BODY, published=published))
    ctx = await run_analysis(ctx, nli=FakeNLI(NLI))
    assert ctx.source_status == SourceStatus.CONFIRMED and 0.0 < ctx.confidence <= 1.0
    for phrase in phrases + ["not part of any verdict"]:
        assert phrase in ctx.reasoning
    assert not any(w in ctx.reasoning.lower() for w in ("fake", "misleading"))
    assert ctx.analysis.pipeline_version == VERIFICATION_PIPELINE_VERSION
    assert ctx.analysis.claim_scope == ClaimScope.HEADLINE_WITH_BODY
    scope = ctx.analysis.source_scope
    assert (scope.verification_mode, scope.claimed_source, scope.primary_publisher) == (
        "CLAIMED_SOURCE", "prothomalo.com", "prothomalo.com",
    )


async def test_not_found_is_not_a_false_verdict_and_its_strength_is_search_completeness():
    ctx = await run_analysis(make_context(HEADLINE, body=BODY, search_adequate=True))
    assert ctx.source_status == SourceStatus.NOT_FOUND and ctx.content_status is None
    assert "does not establish that the claim is false" in ctx.reasoning
    assert "Body similarity is unavailable" in ctx.reasoning and "Search: 3 call(s)" in ctx.reasoning
    assert ctx.confidence == 1.0  # 3 completed of 4 attempted, one empty: (3 + 1)/4


@pytest.mark.parametrize("setup,reason", [
    (dict(search_errors=4, search_success=0, search_success_empty=0), "The news search failed."),
    (dict(fetch_attempted=2, fetch_errors=2), "The candidate articles could not be retrieved."),
    (dict(), "The search did not complete adequately."),
])
async def test_incomplete_checks_say_why_and_carry_no_findings(setup, reason):
    ctx = make_context(HEADLINE, published_date=date(2026, 6, 7), search_adequate=False)
    for k, v in setup.items():
        setattr(ctx, k, v)
    ctx = await run_analysis(ctx)
    assert ctx.source_status == SourceStatus.INCOMPLETE and ctx.confidence == 0.0
    assert (ctx.content_status, ctx.date_status) == (None, None)
    assert ctx.analysis.source_scope.incomplete_reason == reason
    assert "could not be completed" in ctx.reasoning


async def test_a_run_whose_source_check_never_finished_is_incomplete():
    ctx = make_context(HEADLINE)
    ctx.content_status = "MATCHED"  # leftover from a partial run is cleared
    out = await ResultAssemblyStage().execute(ctx)
    assert out.source_status == SourceStatus.INCOMPLETE
    assert out.headline_check_status == HeadlineCheckStatus.SOURCE_CHECK_INCOMPLETE
    assert out.content_status is None and out.analysis.source_basis


def verified_context(*publishers, **kwargs):
    ctx = make_context(HEADLINE, **kwargs)
    ctx.verification_mode = source_policy.VERIFIED_SOURCES
    ctx.raw_claimed_source = ""
    ctx.verified_scope = source_policy.VerifiedScope(
        [source_policy.VerifiedPublisher(p, p, [p], {}) for p in publishers], fingerprint="fp"
    )
    return ctx


async def test_verified_sources_results_never_imply_a_claimed_outlet():
    found = await run_analysis(
        verified_context("prothomalo.com", "jugantor.com", top=article(TITLE, BODY, published=None),
                         published_date=date(2026, 6, 7)),
        nli=FakeNLI(NLI),
    )
    assert "Related reports found in verified sources" in found.reasoning and "from prothomalo.com" in found.reasoning
    assert "article's own publication date could not be determined" in found.reasoning
    scope = found.analysis.source_scope
    assert scope.claimed_source is None and scope.scope_fingerprint == "fp"
    assert scope.eligible_publishers == ["prothomalo.com", "jugantor.com"] and scope.evidence_publishers == ["prothomalo.com"]

    not_found = await run_analysis(verified_context("prothomalo.com", search_adequate=True))
    assert "No matching report was found in the verified sources searched" in not_found.reasoning
    empty = await run_analysis(verified_context(search_adequate=False))
    assert empty.analysis.source_scope.incomplete_reason == "No active verified sources were available to search."
    assert "Verification could not be completed: No active verified sources" in empty.reasoning


async def test_an_assembly_failure_is_a_classification_error():
    ctx = make_context(HEADLINE)
    ctx.analysis = None
    with pytest.raises(ClassificationError):
        await ResultAssemblyStage().execute(ctx)
