"""
tests/unit/test_classifier.py
=============================
S11 and the pure decision functions behind it. Source, Content and Date are
decided separately; none of them is an overall verdict.

Scenario coverage over the real analysis stages lives in
test_scope_aware_scoring.py; this file pins the decision rules themselves.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.core.config import get_settings
from app.core.constants import (
    ClaimScope,
    ContentStatus,
    DateStatus,
    MetricState,
    SourceStatus,
)
from app.features.verification.analysis.decisions import (
    DecisionInputs,
    Metric,
    assess_correspondence,
    check_strength,
    decide_content,
    decide_date,
    decide_source,
    search_adequate,
)
from app.features.verification.pipeline.stages.s11_classifier import ClassifierStage
from app.features.verification.schemas import ContentCheck, ContentFinding
from pipeline_helpers import article, make_context

T = get_settings().classification


def M(v: float | None, state: MetricState = MetricState.COMPUTED) -> Metric:
    return Metric(state if v is not None else MetricState.UNAVAILABLE, v)


def inputs(**kw) -> DecisionInputs:
    base = dict(
        scope=ClaimScope.HEADLINE_ONLY,
        headline_similarity=M(0.9),
        headline_keyword_coverage=M(1.0),
        passage_keyword_coverage=M(1.0),
        entity_coverage=Metric(MetricState.NOT_APPLICABLE),
    )
    base.update(kw)
    return DecisionInputs(**base)


# ── source ──────────────────────────────────────────────────────────────


def test_source_confirmed_needs_a_corresponding_report():
    corr = assess_correspondence(inputs(), T)
    assert corr.level == "STRONG"
    status, _ = decide_source(has_evidence=True, search_adequate=True, retrieval_failed=False, correspondence=corr)
    assert status == SourceStatus.CONFIRMED


def test_same_outlet_topic_similarity_is_not_correspondence():
    weak = inputs(headline_similarity=M(0.5), headline_keyword_coverage=M(0.2), passage_keyword_coverage=M(0.3))
    corr = assess_correspondence(weak, T)
    assert corr.level == "NONE"
    assert decide_source(has_evidence=True, search_adequate=True, retrieval_failed=False, correspondence=corr)[0] == SourceStatus.NOT_FOUND
    # ...but if the search itself was inadequate, absence is not established
    assert decide_source(has_evidence=True, search_adequate=False, retrieval_failed=False, correspondence=corr)[0] == SourceStatus.INCOMPLETE


def test_altered_detail_still_corresponds_when_title_matches():
    # correspondence ignores body metrics and the content comparison entirely
    corr = assess_correspondence(inputs(body_similarity=M(0.0)), T)
    assert corr.level == "STRONG"


def test_no_measurements_is_unknown_so_incomplete_not_not_found():
    blank = DecisionInputs(scope=ClaimScope.HEADLINE_ONLY)
    corr = assess_correspondence(blank, T)
    assert corr.level == "UNKNOWN"
    assert decide_source(has_evidence=True, search_adequate=True, retrieval_failed=False, correspondence=corr)[0] == SourceStatus.INCOMPLETE


@pytest.mark.parametrize(
    "has_evidence,adequate,retrieval_failed,expected",
    [
        (False, True, False, SourceStatus.NOT_FOUND),
        (False, False, False, SourceStatus.INCOMPLETE),
        (False, None, False, SourceStatus.INCOMPLETE),
        (False, True, True, SourceStatus.INCOMPLETE),  # pages could not be fetched
    ],
)
def test_no_evidence_outcomes(has_evidence, adequate, retrieval_failed, expected):
    assert decide_source(has_evidence=has_evidence, search_adequate=adequate, retrieval_failed=retrieval_failed, correspondence=None)[0] == expected


def test_search_adequacy_needs_enough_completed_calls():
    assert search_adequate(10, 8, min_calls=2, min_ratio=0.5)
    assert not search_adequate(10, 1, min_calls=2, min_ratio=0.5)
    assert not search_adequate(10, 4, min_calls=2, min_ratio=0.5)
    assert not search_adequate(0, 0, min_calls=2, min_ratio=0.5)


# ── content ─────────────────────────────────────────────────────────────


def F(status: str, part: str = "headline", **kw) -> ContentFinding:
    return ContentFinding(part=part, claim_text="দাবি", status=status, explanation="কারণ", **kw)


def check(*findings: ContentFinding, **kw) -> ContentCheck:
    return ContentCheck(method="test", findings=list(findings), **kw)


def test_every_supported_statement_is_matched():
    status, basis = decide_content(check(F("SUPPORTED"), F("SUPPORTED", "body")))
    assert status == ContentStatus.MATCHED and len(basis) == 2


def test_one_concrete_difference_is_altered_even_beside_support_and_open_statements():
    status, basis = decide_content(
        check(F("SUPPORTED"), F("INSUFFICIENT_EVIDENCE", "body"), F("CONTRADICTED", "body", kind="numbers"))
    )
    assert status == ContentStatus.ALTERED and basis == ['body "দাবি": কারণ']


@pytest.mark.parametrize(
    "result",
    [
        check(F("SUPPORTED"), F("INSUFFICIENT_EVIDENCE", "body")),  # one statement not established
        check(F("SUPPORTED"), unchecked_statements=3),              # part of the body not compared
        check(reason="no comparable text"),                         # comparison could not run
        check(),                                                    # nothing compared
    ],
)
def test_missing_or_partial_evidence_is_incomplete_never_altered(result):
    status, basis = decide_content(result)
    assert status == ContentStatus.INCOMPLETE
    assert basis or not result.findings


# ── date ────────────────────────────────────────────────────────────────


def test_date_rules():
    d = date(2026, 6, 7)
    assert decide_date(d, d, source_confirmed=True) == DateStatus.MATCHED
    assert decide_date(d, date(2026, 6, 8), source_confirmed=True) == DateStatus.MISMATCHED
    assert decide_date(d, None, source_confirmed=True) == DateStatus.INCOMPLETE
    assert decide_date(None, d, source_confirmed=True) is None
    assert decide_date(d, d, source_confirmed=False) is None


# ── confidence is a measurement summary, not a probability ──────────────


def test_check_strength_is_the_mean_of_applicable_measurements():
    assert check_strength([1.0, 0.5, None]) == 0.75
    assert check_strength([None, None]) == 0.0


@pytest.mark.asyncio
async def test_classifier_never_emits_an_overall_verdict_and_explains_with_evidence():
    t = "সরকার শুল্ক কমিয়েছে ১০ শতাংশ"
    ctx = make_context("সরকার শুল্ক কমিয়েছে ২০ শতাংশ", top=article(t, t + "।"))
    from pipeline_helpers import run_analysis

    ctx = await run_analysis(ctx)
    assert ctx.content_status == ContentStatus.ALTERED
    # the reasoning cites the actual discrepancy, not a score-derived guess
    assert "২০" in ctx.reasoning and "১০" in ctx.reasoning
    assert "different topic focus" not in ctx.reasoning
    assert not hasattr(ctx, "overall_verdict")
    assert ctx.reasoning.rstrip().endswith("Verdict: source CONFIRMED, content ALTERED, date N/A.")


@pytest.mark.asyncio
async def test_classifier_without_articles_and_inadequate_search_is_incomplete():
    ctx = make_context("শিরোনাম", search_adequate=False)
    ctx = await ClassifierStage().execute(ctx)
    assert ctx.source_status == SourceStatus.INCOMPLETE
    assert ctx.confidence == 0.0
    assert ctx.content_status is None and ctx.date_status is None
