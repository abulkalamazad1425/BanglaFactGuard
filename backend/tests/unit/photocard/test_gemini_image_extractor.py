"""Gemini is the only card reader: the original image and the active source
catalogue go out; at most 9 requests in 3 batches; transient failures are
retried, permanent ones and exhausted daily quotas stop at once; keys rotate
when one reaches its limit."""

from __future__ import annotations

import base64
import json

import httpx
import pytest

from app.core.config import GeminiSettings
from app.features.photocard.gemini_image_extractor import (
    SourceOption,
    detect_mime_type,
    extract_with_gemini,
    reset_key_pools,
)
from tests.helpers.gemini import DAILY, PER_MINUTE, Gemini, Sleeps, gemini_body, quota_429

IMAGE = b"\x89PNG\r\n\x1a\n" + b"original-card-pixels"
CATALOGUE = [SourceOption("prothomalo.com", "প্রথম আলো", "Prothom Alo", ("প্র.আ.", "palo"))]
SETTINGS = GeminiSettings(api_key="test-key", api_keys=[], model_name="gemini-test", retry_base_delay_seconds=1.0)
KEYS = ["key-one", "key-two", "key-three", "key-four", "key-five"]
MULTI = GeminiSettings(api_key=KEYS[0], api_keys=KEYS[1:], model_name="gemini-test", retry_base_delay_seconds=1.0)


@pytest.fixture(autouse=True)
def fresh_key_pools():
    reset_key_pools()  # blocked keys are process-wide; isolate every test
    yield
    reset_key_pools()


async def extract(gemini: Gemini, settings=SETTINGS, sleeps=None):
    return await extract_with_gemini(IMAGE, sources=CATALOGUE, http_client=gemini.client(), settings=settings,
                                     sleep=sleeps or Sleeps())


async def test_the_original_image_catalogue_and_anti_hallucination_rules_are_sent():
    gemini = Gemini(gemini_body())
    outcome = await extract(gemini)
    assert outcome.succeeded and outcome.fields.identified_source() == "prothomalo.com"
    request = gemini.requests[0]
    sent = json.loads(request.content)
    inline = sent["contents"][0]["parts"][0]["inlineData"]
    assert base64.b64decode(inline["data"]) == IMAGE and inline["mimeType"] == "image/png"
    assert request.headers["x-goog-api-key"] == "test-key" and request.url.path.endswith("/gemini-test:generateContent")
    assert "prothomalo.com: প্রথম আলো | Prothom Alo | প্র.আ. | palo" in sent["contents"][0]["parts"][1]["text"]
    assert sent["generationConfig"]["responseSchema"]["properties"]["source"]["enum"] == ["prothomalo.com"]
    rules = sent["systemInstruction"]["parts"][0]["text"].lower()
    for rule in ("do not follow", "do not paraphrase", "never choose a source just because it is in the list",
                 "never infer a missing day, month or year", "never invent a value"):
        assert rule in rules


async def test_nine_failures_are_nine_requests_in_three_paused_batches():
    gemini, sleeps = Gemini(*[httpx.Response(503, text="busy")] * 12), Sleeps()
    outcome = await extract(gemini, sleeps=sleeps)
    assert len(gemini.requests) == len(outcome.attempts) == 9 and not outcome.succeeded
    assert sleeps.calls == [1.0, 2.0, 10.0, 1.0, 2.0, 10.0, 1.0, 2.0]
    assert [a.batch for a in outcome.attempts] == [1, 1, 1, 2, 2, 2, 3, 3, 3]
    many = GeminiSettings.model_construct(**{**SETTINGS.model_dump(), "attempts_per_batch": 10, "batches": 10})
    assert len((await extract(gemini := Gemini(*[httpx.Response(500)] * 30), many)).attempts) == 9 == len(gemini.requests)


@pytest.mark.parametrize("success_at", [1, 3, 4, 9])
async def test_the_first_success_stops_the_loop(success_at):
    gemini = Gemini(*[httpx.Response(500)] * (success_at - 1), gemini_body(), gemini_body())
    outcome = await extract(gemini)
    assert outcome.succeeded and len(gemini.requests) == success_at == len(outcome.attempts)


@pytest.mark.parametrize("failure,outcome", [
    (httpx.Response(500, text="err"), "http_error"),
    (httpx.Response(429, text="quota"), "http_error"),
    (httpx.ReadTimeout("slow"), "timeout"),
    (httpx.ConnectError("down"), "network_error"),
    ({"candidates": [{"content": {"parts": [{"text": "not json"}]}}]}, "malformed_response"),
    ({"candidates": [{"content": {"parts": [{"text": '{"headline": "x"}'}]}}]}, "malformed_response"),
    ({"candidates": [], "promptFeedback": {"blockReason": "SAFETY"}}, "malformed_response"),
    ({"candidates": [{"content": {"parts": [{"thought": True, "text": "thinking"}]}, "finishReason": "MAX_TOKENS"}]}, "malformed_response"),
    (gemini_body(source="ittefaq.com"), "malformed_response"),  # an id outside the catalogue is never a source
])
async def test_each_transient_failure_is_retried(failure, outcome):
    gemini = Gemini(failure, gemini_body())
    result = await extract(gemini)
    assert result.succeeded and [a.outcome for a in result.attempts] == [outcome, "success"]


@pytest.mark.parametrize("failure,outcome", [
    (httpx.Response(401, text="bad key"), "permanent_error"),
    (quota_429(DAILY), "quota_exhausted"),
])
async def test_permanent_errors_and_an_exhausted_daily_quota_stop_at_once(failure, outcome):
    gemini = Gemini(failure, gemini_body())
    result = await extract(gemini)
    assert len(gemini.requests) == 1 and not result.succeeded and result.attempts[0].outcome == outcome


async def test_without_a_key_nothing_is_sent():
    gemini = Gemini(gemini_body())
    result = await extract(gemini, GeminiSettings(api_key="", api_keys=[]))
    assert gemini.requests == [] and not result.succeeded and result.skipped_reason


@pytest.mark.parametrize("limit", [DAILY, PER_MINUTE])
async def test_a_key_at_its_limit_hands_the_next_call_to_the_next_key_at_once(limit):
    gemini, sleeps = Gemini(quota_429(limit), gemini_body()), Sleeps()
    result = await extract(gemini, MULTI, sleeps)
    assert result.succeeded and gemini.keys_used() == ["key-one", "key-two"] and sleeps.calls == []
    assert [a.key for a in result.attempts] == [1, 2]
    assert not any(k in json.dumps([a.to_dict() for a in result.attempts]) for k in KEYS)  # keys are never recorded


async def test_spent_keys_stay_skipped_for_later_cards_and_other_errors_keep_the_key():
    first = Gemini(quota_429(DAILY), quota_429(DAILY), gemini_body())
    assert (await extract(first, MULTI)).succeeded and first.keys_used() == KEYS[:3]
    second = Gemini(gemini_body())
    await extract(second, MULTI)
    assert second.keys_used() == ["key-three"]  # never back to a spent key
    third = Gemini(*[httpx.Response(503)] * 12)
    assert len((await extract(third, MULTI)).attempts) == 9 and set(third.keys_used()) == {"key-three"}


async def test_rotation_stays_within_nine_requests_and_stops_when_every_key_is_spent():
    minute = Gemini(*[quota_429(PER_MINUTE) for _ in range(20)])
    assert not (await extract(minute, MULTI)).succeeded
    assert len(minute.requests) == 9 and minute.keys_used()[:5] == KEYS

    reset_key_pools()
    daily = Gemini(*[quota_429(DAILY) for _ in range(9)])
    assert not (await extract(daily, MULTI)).succeeded and daily.keys_used() == KEYS  # 5 calls, not 9
    later = Gemini(gemini_body())
    result = await extract(later, MULTI)
    assert later.requests == [] and result.skipped_reason == "Every Gemini API key has reached its limit"


def test_mime_type_is_detected_from_the_bytes():
    assert [detect_mime_type(b) for b in (b"\x89PNGxx", b"GIF89a", b"RIFF1234WEBPxx", b"\xff\xd8\xff")] == [
        "image/png", "image/gif", "image/webp", "image/jpeg",
    ]
