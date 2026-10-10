"""One source policy for registration, photo cards and S01: a claim names a
usable outlet (CLAIMED_SOURCE) or is checked against the active verified
sources (VERIFIED_SOURCES) - never an unrestricted search."""

from unittest.mock import AsyncMock

import pytest

from app.features.verification import source_policy as sp
from tests.helpers.pipeline import FakeSourceRepo, source_record

REPO = FakeSourceRepo(
    source_record("prothomalo.com", aliases=["প্রথম আলো", "https://en.prothomalo.com"], base_url="https://www.prothomalo.com"),
    source_record("jugantor.com", active=False),
    source_record("samakal.com"),
)


@pytest.mark.parametrize("raw,mode,canonical,reason", [
    ("প্রথম আলো", sp.CLAIMED_SOURCE, "prothomalo.com", sp.REASON_SELECTED),
    ("   ", sp.VERIFIED_SOURCES, None, sp.REASON_NOT_SUPPLIED),
    (None, sp.VERIFIED_SOURCES, None, sp.REASON_NOT_SUPPLIED),
    ("অপরিচিত উৎস", sp.VERIFIED_SOURCES, None, sp.REASON_UNRECOGNIZED),
    ("jugantor.com", sp.VERIFIED_SOURCES, None, sp.REASON_INACTIVE),
])
async def test_resolution_mode_and_reason(raw, mode, canonical, reason):
    r = await sp.resolve_source(raw, REPO)
    assert (r.mode, r.canonical, r.reason) == (mode, canonical, reason)
    assert r.is_fallback is (mode == sp.VERIFIED_SOURCES)


async def test_a_registry_lookup_hiccup_keeps_the_claimed_path():
    repo = FakeSourceRepo()
    repo.get_by_canonical_name = AsyncMock(side_effect=RuntimeError("db"))
    r = await sp.resolve_source("https://www.thedailystar.net/news/1", repo, selected_reason=sp.REASON_DETECTED)
    assert (r.mode, r.canonical, r.reason) == (sp.CLAIMED_SOURCE, "thedailystar.net", sp.REASON_DETECTED)


async def test_verified_scope_lists_active_publishers_with_their_domains():
    scope = await sp.load_verified_scope(REPO)
    assert [p.canonical for p in scope.publishers] == ["prothomalo.com", "samakal.com"]
    assert scope.publishers[0].domains == ["prothomalo.com", "en.prothomalo.com"]
    assert scope.all_domains == ["prothomalo.com", "en.prothomalo.com", "samakal.com"]
    assert scope.publisher_for_url("https://en.prothomalo.com/a/1").canonical == "prothomalo.com"
    assert scope.publisher_for_url("https://prothomalo.com.evil.net/a") is None
    assert scope.publisher_for_url("http://[invalid") is None


async def test_the_identity_changes_with_the_registry_and_never_collides_with_a_claimed_source():
    before = await sp.load_verified_scope(REPO)
    after = await sp.load_verified_scope(FakeSourceRepo(*REPO.records[:1]))
    assert before.fingerprint != after.fingerprint
    key = sp.verified_identity_key(before)
    assert sp.is_verified_identity_key(key) and not sp.is_verified_identity_key("prothomalo.com")
    empty = await sp.load_verified_scope(FakeSourceRepo())
    assert empty.empty and sp.verified_identity_key(sp.VerifiedScope()) == "verified-sources:empty"


def test_source_config_carries_selectors_and_allowed_channels():
    record = source_record("prothomalo.com", body_selectors=None, aliases=["প্রথম আলো", "m.prothomalo.com"],
                           internal_search_url="https://www.prothomalo.com/search?q={query}")
    config = sp.source_config_for(record)
    assert config["body_selectors"] == [] and config["internal_search_url"].endswith("{query}")
    assert config["allowed_domains"] == ["prothomalo.com", "m.prothomalo.com"]
