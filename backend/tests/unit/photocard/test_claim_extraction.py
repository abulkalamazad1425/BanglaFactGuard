"""The card's values become the claim: headline, an ACTIVE verified source
(or verified-sources mode) and the printed date. An API failure and a card
without a usable headline are distinct outcomes, and neither is retried."""

from __future__ import annotations

import uuid
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.core.config import GeminiSettings
from app.features.photocard import claim_extraction
from app.features.photocard.claim_extraction import (
    API_FAILURE_MESSAGE,
    INVALID_CONTENT_MESSAGE,
    INVALID_HEADLINE_MESSAGE,
    STATUS_API_FAILED,
    STATUS_INVALID_CONTENT,
    STATUS_SUCCEEDED,
    CardExtraction,
    PhotocardClaimExtractor,
)
from app.features.photocard.gemini_image_extractor import reset_key_pools
from app.features.verification import source_policy
from tests.helpers.gemini import HEADLINE, Gemini, Sleeps, gemini_body

IMAGE = b"\x89PNG\r\n\x1a\n" + b"card"


@pytest.fixture(autouse=True)
def gemini_settings(monkeypatch):
    reset_key_pools()
    real = claim_extraction.get_settings()
    settings = GeminiSettings(api_key="test-key", api_keys=[], model_name="gemini-test", retry_base_delay_seconds=0)
    monkeypatch.setattr(claim_extraction, "get_settings", lambda: real.model_copy(update={"gemini": settings}))
    yield
    reset_key_pools()


def source(canonical="prothomalo.com", *, active=True, **kw):
    return SimpleNamespace(id=uuid.uuid4(), canonical_name=canonical, is_active=active,
                           display_name=kw.get("display_name", "প্রথম আলো"), display_name_en=kw.get("display_name_en", "Prothom Alo"),
                           aliases=kw.get("aliases", ["প্রথম আলো", "Prothom-Alo"]))


def repo(*sources, deactivated_meanwhile=False):
    sources = sources or (source(), source("jugantor.com", display_name="যুগান্তর", display_name_en="Jugantor",
                                           aliases=["দৈনিক যুগান্তর"]))
    r = MagicMock(list_active=AsyncMock(return_value=[s for s in sources if s.is_active]))
    r.get_by_canonical_name = AsyncMock(side_effect=lambda c: source(c, active=False) if deactivated_meanwhile
                                        else next((s for s in sources if s.canonical_name == c), None))
    return r


async def extract(gemini: Gemini, source_repo=None) -> CardExtraction:
    return await PhotocardClaimExtractor(source_repo=source_repo or repo(), http_client=gemini.client(), sleep=Sleeps()).extract(IMAGE)


async def test_card_values_become_the_claim_and_only_active_sources_are_offered():
    inactive = source("ittefaq.com", active=False, display_name="ইত্তেফাক", aliases=["দৈনিক ইত্তেফাক"])
    gemini = Gemini(gemini_body())
    result = await extract(gemini, repo(source(), inactive))
    assert (result.status, result.attempts, result.model_version) == (STATUS_SUCCEEDED, 1, "gemini-test")
    assert result.headline == HEADLINE  # quotes, dash, digits and punctuation untouched
    assert result.source.canonical_name == "prothomalo.com" and result.published_date == date(2026, 10, 5)
    assert result.details["response"]["date"] == "০৫ অক্টোবর, ২০২৬" and result.raw_source_text == "প্রথম আলো logo"
    assert "ittefaq.com" not in gemini.requests[0].content.decode()
    alias = await extract(Gemini(gemini_body(source="jugantor.com", source_evidence="দৈনিক যুগান্তর")))
    assert alias.source.canonical_name == "jugantor.com"


async def test_a_missing_or_partial_date_is_no_date_not_a_failure():
    for body in (gemini_body(date=None, date_status="MISSING"), gemini_body(date="৫ অক্টোবর")):
        gemini = Gemini(body)
        result = await extract(gemini)
        assert result.status == STATUS_SUCCEEDED and result.published_date is None and len(gemini.requests) == 1


async def test_an_api_failure_is_its_own_outcome():
    result = await extract(Gemini(httpx.Response(401, text="bad key")))
    assert (result.status, result.failure_code, result.failure_message) == (STATUS_API_FAILED, "gemini_unavailable", API_FAILURE_MESSAGE)


@pytest.mark.parametrize("fields,reason", [
    ({"source": None, "source_status": "NOT_VISIBLE"}, "SOURCE_NOT_DETECTED"),
    ({"source": None, "source_status": "NOT_RECOGNIZED", "source_evidence": "Somoy TV"}, "SOURCE_UNRECOGNIZED"),
    ({"source": "prothomalo.com", "source_status": "UNCLEAR"}, "SOURCE_UNRECOGNIZED"),
])
async def test_a_readable_headline_without_a_verified_source_uses_the_verified_sources(fields, reason):
    gemini = Gemini(gemini_body(**fields), gemini_body())
    result = await extract(gemini)
    assert (result.status, result.source, result.source_reason) == (STATUS_SUCCEEDED, None, reason)
    assert len(gemini.requests) == 1 and result.published_date == date(2026, 10, 5)
    if "source_evidence" in fields:
        assert result.raw_source_text == "Somoy TV"  # provenance only, never a source


async def test_a_source_deactivated_meanwhile_is_not_accepted():
    result = await extract(Gemini(gemini_body()), repo(source(), deactivated_meanwhile=True))
    assert (result.status, result.source, result.source_reason) == (STATUS_SUCCEEDED, None, "SOURCE_INACTIVE")


@pytest.mark.parametrize("fields,code", [
    ({"headline": None, "headline_status": "MISSING"}, "headline_missing"),
    ({"headline": "ছোট", "headline_status": "PRESENT"}, "headline_missing"),
    ({"headline": "১২৩৪৫৬৭৮৯০", "headline_status": "PRESENT"}, "headline_missing"),  # no letters
    ({"source": None, "source_status": "NOT_VISIBLE"}, "source_not_identified"),
    ({"source": "prothomalo.com", "source_status": "UNCLEAR"}, "source_not_identified"),
    ({"headline": None, "headline_status": "UNREADABLE", "source": None, "source_status": "UNCLEAR"},
     "headline_and_source_missing"),
])
async def test_with_the_fallback_off_a_card_needs_a_headline_and_a_verified_source(monkeypatch, fields, code):
    monkeypatch.setattr(source_policy, "fallback_enabled", lambda: False)
    gemini = Gemini(gemini_body(**fields), gemini_body())
    result = await extract(gemini)
    assert (result.status, result.failure_code, result.failure_message) == (STATUS_INVALID_CONTENT, code, INVALID_CONTENT_MESSAGE)
    assert len(gemini.requests) == 1 and result.headline is None and result.source is None  # never retried


async def test_with_the_fallback_on_a_missing_headline_is_still_rejected():
    gemini = Gemini(gemini_body(headline=None, headline_status="MISSING"))
    result = await extract(gemini)
    assert result.status == STATUS_INVALID_CONTENT and result.failure_message == INVALID_HEADLINE_MESSAGE
    assert CardExtraction(status=STATUS_SUCCEEDED).failure_message is None
