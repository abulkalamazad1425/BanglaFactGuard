"""
tests/unit/test_claim_scope.py
================================
Business rule: a photo-card claim is always HEADLINE_ONLY — verified against
its extracted headline alone, never a body or caption, with nothing
synthesised to stand in for one. A SOURCE_BASED text claim is
HEADLINE_WITH_BODY whenever the user supplied body text.

Covers:
- `compute_claim_hash` folds `claim_scope` into claim identity, so a
  HEADLINE_ONLY run and a HEADLINE_WITH_BODY run of the same headline+source
  never collide in the cache.
- `build_context` infers scope from whether `news_body` was given, and an
  explicit `claim_scope=HEADLINE_ONLY` always drops any body passed alongside
  it — the defense-in-depth a photo-card caller relies on.
- S03 (query generation) never uses claim body text when `claim_scope` is
  HEADLINE_ONLY, even if `normalized_body` is somehow populated.
"""

import pytest

from app.core.constants import ClaimScope
from app.features.verification.pipeline.context import build_context
from app.features.verification.pipeline.stages.s03_query_generator import (
    QueryGeneratorStage,
)
from app.shared.utils.hashing import compute_claim_hash


# ─── compute_claim_hash ──────────────────────────────────────────────────


def test_hash_differs_between_headline_only_and_headline_with_body():
    h1 = compute_claim_hash("একই শিরোনাম", "prothomalo.com", ClaimScope.HEADLINE_ONLY)
    h2 = compute_claim_hash(
        "একই শিরোনাম", "prothomalo.com", ClaimScope.HEADLINE_WITH_BODY
    )
    assert h1 != h2


def test_hash_stable_for_same_scope():
    h1 = compute_claim_hash("একই শিরোনাম", "prothomalo.com", ClaimScope.HEADLINE_ONLY)
    h2 = compute_claim_hash("একই শিরোনাম", "prothomalo.com", ClaimScope.HEADLINE_ONLY)
    assert h1 == h2


# ─── build_context scope inference ──────────────────────────────────────


def test_infers_headline_with_body_when_body_given():
    context = build_context(
        headline="শিরোনাম", claimed_source="prothomalo.com", news_body="বডি টেক্সট"
    )
    assert context.claim_scope == ClaimScope.HEADLINE_WITH_BODY
    assert context.raw_news_body == "বডি টেক্সট"


def test_infers_headline_only_when_no_body():
    context = build_context(headline="শিরোনাম", claimed_source="prothomalo.com")
    assert context.claim_scope == ClaimScope.HEADLINE_ONLY
    assert context.raw_news_body is None


def test_infers_headline_only_when_body_is_blank():
    context = build_context(
        headline="শিরোনাম", claimed_source="prothomalo.com", news_body="   "
    )
    assert context.claim_scope == ClaimScope.HEADLINE_ONLY


def test_explicit_headline_only_drops_body_even_if_passed():
    """A photo-card caller passing both claim_scope=HEADLINE_ONLY and a body
    (which should never happen, but might via a future bug) must still get
    no body threaded into the pipeline — the override wins, not the body."""
    context = build_context(
        headline="শিরোনাম",
        claimed_source="prothomalo.com",
        news_body="এই বডি টেক্সট ব্যবহার করা উচিত নয়",
        claim_scope=ClaimScope.HEADLINE_ONLY,
    )
    assert context.claim_scope == ClaimScope.HEADLINE_ONLY
    assert context.raw_news_body is None


# ─── S03 — query generation respects scope ──────────────────────────────


@pytest.mark.asyncio
async def test_s03_skips_body_queries_when_headline_only():
    context = build_context(
        headline="বাজেট ২০২৬ ঘোষণা",
        claimed_source="prothomalo.com",
        news_body="অর্থমন্ত্রী জাতীয় সংসদে নতুন অর্থ বছরের বাজেট পেশ করছেন।",
        claim_scope=ClaimScope.HEADLINE_ONLY,
    )
    context.normalized_headline = context.raw_headline
    context.normalized_source = "prothomalo.com"
    context.normalized_body = "অর্থমন্ত্রী জাতীয় সংসদে নতুন অর্থ বছরের বাজেট পেশ করছেন।"

    stage = QueryGeneratorStage()
    context = await stage.execute(context)

    from app.core.constants import QueryType

    body_queries = [
        q for q, t in context.search_queries if t == QueryType.BODY_SUMMARY.value
    ]
    assert body_queries == []


@pytest.mark.asyncio
async def test_s03_skips_body_queries_when_headline_with_body():
    context = build_context(
        headline="বাজেট ২০২৬ ঘোষণা",
        claimed_source="prothomalo.com",
        news_body="অর্থমন্ত্রী জাতীয় সংসদে নতুন অর্থ বছরের বাজেট পেশ করছেন। শিক্ষা খাতে বরাদ্দ বৃদ্ধি।",
    )
    context.normalized_headline = context.raw_headline
    context.normalized_source = "prothomalo.com"
    context.normalized_body = context.raw_news_body

    stage = QueryGeneratorStage()
    context = await stage.execute(context)

    from app.core.constants import QueryType

    body_queries = [
        q for q, t in context.search_queries if t == QueryType.BODY_SUMMARY.value
    ]
    assert body_queries == []


# S08 scope handling (no body similarity / weighting for HEADLINE_ONLY, chunked
# body comparison for HEADLINE_WITH_BODY) is covered in
# test_scope_aware_scoring.py; the photo-card flow always building a
# HEADLINE_ONLY context is covered in test_photocard_background.py.
