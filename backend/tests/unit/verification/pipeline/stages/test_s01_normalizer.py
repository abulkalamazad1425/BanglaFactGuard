"""S01: normalised claim, verification mode and the single claim identity.
An unresolved source never silently runs an unrestricted search."""

from datetime import date

import pytest

from app.core.exceptions import NormalizationError
from app.features.verification import source_policy
from app.features.verification.pipeline.context import build_context
from app.features.verification.pipeline.stages.s01_normalizer import InputNormalizerStage
from app.shared.utils.hashing import compute_claim_hash
from tests.helpers.pipeline import FakeSourceRepo, source_record

REPO = FakeSourceRepo(
    source_record("prothomalo.com", body_selectors=["div.story"], aliases=["প্রথম আলো"]),
    source_record("customportal.com", aliases=["কাস্টম পোর্টাল"]),
    source_record("jugantor.com", active=False),
)


async def normalise(headline="  ঢাকায়  বৃষ্টি ​", source="প্রথম আলো", repo=REPO, **kw):
    return await InputNormalizerStage(source_repo=repo).execute(build_context(headline, source, **kw))


async def test_claimed_source_claim_is_normalised_and_identified():
    ctx = await normalise(news_body=" বডি  এক ", published_date=date(2026, 6, 7))
    assert (ctx.normalized_headline, ctx.normalized_body) == ("ঢাকায় বৃষ্টি", "বডি এক")
    assert ctx.verification_mode == source_policy.CLAIMED_SOURCE and ctx.normalized_source == "prothomalo.com"
    assert ctx.source_config["body_selectors"] == ["div.story"]
    assert ctx.content_hash == compute_claim_hash(
        "ঢাকায় বৃষ্টি", "prothomalo.com", ctx.claim_scope, body="বডি এক", published_date=date(2026, 6, 7)
    )


@pytest.mark.parametrize("source,canonical", [
    ("https://www.thedailystar.net/news/bangladesh-123", "thedailystar.net"),  # URL
    ("কাস্টম পোর্টাল", "customportal.com"),                                    # registry alias
])
async def test_source_resolution_paths(source, canonical):
    assert (await normalise(source=source)).normalized_source == canonical


async def test_empty_headline_is_rejected():
    with pytest.raises(NormalizationError):
        await normalise(headline="   ​   ")


@pytest.mark.parametrize("source,reason", [
    ("", source_policy.REASON_NOT_SUPPLIED),
    ("অপরিচিত উৎস", source_policy.REASON_UNRECOGNIZED),
    ("jugantor.com", source_policy.REASON_INACTIVE),
])
async def test_unusable_source_is_verified_against_the_active_verified_sources(source, reason):
    ctx = await normalise(source=source)
    assert ctx.verification_mode == source_policy.VERIFIED_SOURCES and ctx.source_resolution_reason == reason
    assert ctx.normalized_source is None and ctx.source_config is None
    assert [p.canonical for p in ctx.verified_scope.publishers] == ["customportal.com", "prothomalo.com"]
    assert ctx.content_hash == compute_claim_hash(
        "ঢাকায় বৃষ্টি", source_policy.verified_identity_key(ctx.verified_scope), ctx.claim_scope
    )


async def test_a_callers_reason_for_a_missing_source_is_kept():
    ctx = await normalise(source="", source_resolution_reason="SOURCE_NOT_DETECTED")
    assert ctx.source_resolution_reason == "SOURCE_NOT_DETECTED"


async def test_with_the_fallback_disabled_an_unresolved_source_fails_closed(monkeypatch):
    monkeypatch.setattr(source_policy, "fallback_enabled", lambda: False)
    with pytest.raises(NormalizationError):
        await normalise(source="অপরিচিত উৎস")
