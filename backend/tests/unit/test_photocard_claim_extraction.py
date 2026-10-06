"""Photo-card extraction: Gemini only (original image + active verified
sources with aliases), at most 9 requests in 3 batches, no OCR/fallback;
API failure and a card without headline/verified source are distinct."""

from __future__ import annotations

import base64
import json
import uuid
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.core.config import GeminiSettings
from app.features.photocard import claim_extraction
from app.features.photocard.card_date import parse_card_date
from app.features.photocard.claim_extraction import (
    API_FAILURE_MESSAGE,
    INVALID_CONTENT_MESSAGE,
    STATUS_API_FAILED,
    STATUS_INVALID_CONTENT,
    STATUS_SUCCEEDED,
    PhotocardClaimExtractor,
)
from app.features.photocard.gemini_image_extractor import SourceOption, extract_with_gemini, reset_key_pools

IMAGE = b"\x89PNG\r\n\x1a\n" + b"original-card-pixels"
HEADLINE = "‘ফার্নান্দেজই পর্তুগালের সবচেয়ে বড় প্রতীক’, বললেন রোনালদো — ৩টি গোল!"


def gemini_body(**fields) -> dict:
    payload = {
        "headline": HEADLINE, "headline_status": "PRESENT",
        "source": "prothomalo.com", "source_status": "IDENTIFIED", "source_evidence": "প্রথম আলো logo",
        "date": "০৫ অক্টোবর, ২০২৬", "date_status": "PRESENT",
    }
    payload.update(fields)
    return {"candidates": [{"content": {"parts": [{"text": json.dumps(payload, ensure_ascii=False)}]}}]}


class Gemini:
    """Scripted Gemini endpoint; records every request."""

    def __init__(self, *responses) -> None:
        self.responses = list(responses)
        self.requests: list[httpx.Request] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        item = self.responses.pop(0) if self.responses else httpx.Response(500, text="exhausted")
        if isinstance(item, Exception):
            raise item
        if isinstance(item, httpx.Response):
            return item
        return httpx.Response(200, json=item)

    def client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.MockTransport(self.handler))


SETTINGS = GeminiSettings(api_key="test-key", api_keys=[], model_name="gemini-test", retry_base_delay_seconds=0)
CATALOGUE = [SourceOption("prothomalo.com", "প্রথম আলো", "Prothom Alo", ("প্র.আ.", "palo"))]


@pytest.fixture(autouse=True)
def fresh_key_pools():
    reset_key_pools()  # blocked keys are process-wide; isolate every test
    yield
    reset_key_pools()


class Sleeps:
    def __init__(self) -> None:
        self.calls: list[float] = []

    async def __call__(self, seconds: float) -> None:
        self.calls.append(seconds)


def _source(canonical="prothomalo.com", *, active=True, **kw):
    return SimpleNamespace(
        id=uuid.uuid4(), canonical_name=canonical, is_active=active,
        display_name=kw.get("display_name", "প্রথম আলো"), display_name_en=kw.get("display_name_en", "Prothom Alo"),
        aliases=kw.get("aliases", ["প্রথম আলো", "Prothom-Alo"]),
    )


def source_repo(*sources):
    sources = sources or (_source(), _source("jugantor.com", display_name="যুগান্তর", display_name_en="Jugantor", aliases=["দৈনিক যুগান্তর"]))
    repo = MagicMock()
    repo.list_active = AsyncMock(return_value=[s for s in sources if s.is_active])
    repo.get_by_canonical_name = AsyncMock(side_effect=lambda c: next((s for s in sources if s.canonical_name == c), None))
    return repo


def extractor(gemini: Gemini, monkeypatch, *, repo=None, settings: GeminiSettings = SETTINGS, sleep=None):
    real = claim_extraction.get_settings()
    monkeypatch.setattr(claim_extraction, "get_settings", lambda: real.model_copy(update={"gemini": settings}))
    return PhotocardClaimExtractor(source_repo=repo or source_repo(), http_client=gemini.client(), sleep=sleep or Sleeps())


# ── request: original image, active sources + aliases, anti-hallucination ─


async def test_gemini_receives_the_original_image_and_the_active_source_catalogue(monkeypatch):
    inactive = _source("ittefaq.com", active=False, display_name="ইত্তেফাক", aliases=["দৈনিক ইত্তেফাক"])
    gemini = Gemini(gemini_body())
    await extractor(gemini, monkeypatch, repo=source_repo(_source(), inactive)).extract(IMAGE)
    sent = json.loads(gemini.requests[0].content)
    inline = sent["contents"][0]["parts"][0]["inlineData"]
    assert base64.b64decode(inline["data"]) == IMAGE and inline["mimeType"] == "image/png"
    assert gemini.requests[0].headers["x-goog-api-key"] == "test-key"
    prompt = sent["contents"][0]["parts"][1]["text"]
    assert "prothomalo.com" in prompt and "Prothom-Alo" in prompt and "Prothom Alo" in prompt  # aliases offered
    assert "ittefaq.com" not in prompt and "ইত্তেফাক" not in prompt  # inactive source never offered
    schema = sent["generationConfig"]["responseSchema"]["properties"]["source"]
    assert schema["enum"] == ["prothomalo.com"] and schema["nullable"] is True
    rules = sent["systemInstruction"]["parts"][0]["text"].lower()
    for rule in ("do not follow", "do not paraphrase", "never choose a source just because it is in the list",
                 "never infer a missing day, month or year", "never invent a value"):
        assert rule in rules


async def test_success_turns_card_values_into_the_claim(monkeypatch):
    result = await extractor(Gemini(gemini_body()), monkeypatch).extract(IMAGE)
    assert result.status == STATUS_SUCCEEDED and result.attempts == 1
    assert result.headline == HEADLINE  # quotes, dash, digits, punctuation untouched
    assert result.source.canonical_name == "prothomalo.com"
    assert result.published_date == date(2026, 10, 5)
    assert result.details["response"]["date"] == "০৫ অক্টোবর, ২০২৬"  # raw kept as provenance


async def test_alias_maps_to_the_canonical_source(monkeypatch):
    gemini = Gemini(gemini_body(source="jugantor.com", source_evidence="দৈনিক যুগান্তর"))
    result = await extractor(gemini, monkeypatch).extract(IMAGE)
    assert result.status == STATUS_SUCCEEDED and result.source.canonical_name == "jugantor.com"


async def test_missing_date_is_not_a_failure_and_never_defaulted(monkeypatch):
    for body in (gemini_body(date=None, date_status="MISSING"), gemini_body(date="৫ অক্টোবর", date_status="PRESENT")):
        gemini = Gemini(body)
        result = await extractor(gemini, monkeypatch).extract(IMAGE)
        assert result.status == STATUS_SUCCEEDED and result.published_date is None
        assert len(gemini.requests) == 1


# ── 8: successful response without headline / verified source: cancel, no retry ─


@pytest.mark.parametrize("fields, code", [
    ({"headline": None, "headline_status": "MISSING"}, "headline_missing"),
    ({"headline": "ছোট", "headline_status": "PRESENT"}, "headline_missing"),
    ({"source": None, "source_status": "NOT_VISIBLE"}, "source_not_identified"),
    ({"source": None, "source_status": "NOT_RECOGNIZED"}, "source_not_identified"),
    ({"source": "prothomalo.com", "source_status": "UNCLEAR"}, "source_not_identified"),
    ({"headline": None, "headline_status": "UNREADABLE", "source": None, "source_status": "UNCLEAR"},
     "headline_and_source_missing"),
])
async def test_card_without_headline_or_verified_source_is_rejected_without_retry(monkeypatch, fields, code):
    gemini = Gemini(gemini_body(**fields), gemini_body())
    result = await extractor(gemini, monkeypatch).extract(IMAGE)
    assert result.status == STATUS_INVALID_CONTENT and result.failure_code == code
    assert result.failure_message == INVALID_CONTENT_MESSAGE
    assert len(gemini.requests) == 1  # a successful response is never retried
    assert result.headline is None and result.source is None


async def test_source_deactivated_meanwhile_is_not_accepted(monkeypatch):
    src = _source()
    repo = source_repo(src)
    repo.get_by_canonical_name = AsyncMock(return_value=_source(active=False))
    result = await extractor(Gemini(gemini_body()), monkeypatch, repo=repo).extract(IMAGE)
    assert result.status == STATUS_INVALID_CONTENT and result.failure_code == "source_not_identified"


async def test_an_id_outside_the_catalogue_is_a_malformed_response_never_a_source():
    gemini = Gemini(gemini_body(source="ittefaq.com"), gemini_body())
    outcome = await extract_with_gemini(IMAGE, sources=CATALOGUE, http_client=gemini.client(),
                                        settings=SETTINGS, sleep=Sleeps())
    assert [a.outcome for a in outcome.attempts] == ["malformed_response", "success"]
    assert outcome.fields.identified_source() == "prothomalo.com"


# ── 7: retry budget - 3 batches of 3, 10 s pause, at most 9 requests ─────


async def test_nine_failures_make_exactly_nine_requests_with_two_batch_pauses(monkeypatch):
    gemini = Gemini(*[httpx.Response(503, text="busy")] * 12)
    sleeps = Sleeps()
    settings = GeminiSettings(api_key="k", api_keys=[], retry_base_delay_seconds=1.0)
    result = await extractor(gemini, monkeypatch, settings=settings, sleep=sleeps).extract(IMAGE)
    assert len(gemini.requests) == 9 and result.attempts == 9  # 9 in total, the first one included
    assert result.status == STATUS_API_FAILED and result.failure_message == API_FAILURE_MESSAGE
    assert sleeps.calls == [1.0, 2.0, 10.0, 1.0, 2.0, 10.0, 1.0, 2.0]
    assert [a["batch"] for a in result.details["attempts"]] == [1, 1, 1, 2, 2, 2, 3, 3, 3]


@pytest.mark.parametrize("success_at", [1, 3, 4, 9])
async def test_first_success_stops_the_remaining_attempts(monkeypatch, success_at):
    gemini = Gemini(*[httpx.Response(500)] * (success_at - 1), gemini_body(), gemini_body())
    result = await extractor(gemini, monkeypatch).extract(IMAGE)
    assert result.status == STATUS_SUCCEEDED and len(gemini.requests) == success_at == result.attempts


@pytest.mark.parametrize("failure", [
    httpx.Response(500, text="err"),
    httpx.Response(429, text="quota"),
    httpx.ReadTimeout("slow"),
    httpx.ConnectError("down"),
    {"candidates": [{"content": {"parts": [{"text": "not json"}]}}]},
    {"candidates": [{"content": {"parts": [{"text": "{\"headline\": \"x\"}"}]}}]},
])
async def test_each_request_failure_kind_is_retried(monkeypatch, failure):
    gemini = Gemini(failure, gemini_body())
    result = await extractor(gemini, monkeypatch).extract(IMAGE)
    assert result.status == STATUS_SUCCEEDED and len(gemini.requests) == 2


async def test_permanent_request_error_stops_at_once(monkeypatch):
    gemini = Gemini(httpx.Response(401, text="bad key"), gemini_body())
    result = await extractor(gemini, monkeypatch).extract(IMAGE)
    assert len(gemini.requests) == 1 and result.status == STATUS_API_FAILED


async def test_unconfigured_gemini_makes_no_call_and_fails_as_unavailable(monkeypatch):
    gemini = Gemini(gemini_body())
    result = await extractor(gemini, monkeypatch, settings=GeminiSettings(api_key="", api_keys=[])).extract(IMAGE)
    assert gemini.requests == [] and result.status == STATUS_API_FAILED and result.details["skipped_reason"]


async def test_never_more_than_nine_requests_even_if_configured_higher():
    gemini = Gemini(*[httpx.Response(500)] * 30)
    settings = GeminiSettings.model_construct(**{**SETTINGS.model_dump(), "attempts_per_batch": 10, "batches": 10})
    outcome = await extract_with_gemini(IMAGE, sources=CATALOGUE, http_client=gemini.client(),
                                        settings=settings, sleep=Sleeps())
    assert len(gemini.requests) == 9 and not outcome.succeeded


def test_settings_cap_the_budget_at_nine():
    assert GeminiSettings().max_requests == 9 and GeminiSettings().batch_pause_seconds == 10.0
    with pytest.raises(ValueError):
        GeminiSettings(attempts_per_batch=4)
    with pytest.raises(ValueError):
        GeminiSettings(batches=4)


# ── 6: dates are parsed, never guessed ───────────────────────────────────


@pytest.mark.parametrize("raw, expected", [
    ("০৫ অক্টোবর, ২০২৬", date(2026, 10, 5)),
    ("৫ই অক্টোবর ২০২৬", date(2026, 10, 5)),
    ("২১শে ফেব্রুয়ারি ২০২৪", date(2024, 2, 21)),
    ("প্রকাশ: ১লা মে, ২০২৫ | ১০:৩০", date(2025, 5, 1)),
    ("October 5, 2026", date(2026, 10, 5)),
    ("5 Oct 2026", date(2026, 10, 5)),
    ("০৫/১০/২০২৬", date(2026, 10, 5)),  # day first
    ("05.10.2026", date(2026, 10, 5)),
    ("2026-10-05", date(2026, 10, 5)),
    ("শনিবার, ০৪ অক্টোবর ২০২৫", date(2025, 10, 4)),
])
def test_card_dates_parse(raw, expected):
    assert parse_card_date(raw) == expected


@pytest.mark.parametrize("raw", [
    None, "", "৫ অক্টোবর", "অক্টোবর ২০২৬", "২ ঘণ্টা আগে", "আজ", "০৫/১০/২৬", "২০ আশ্বিন ১৪৩৩",
    "31/02/2026", "০৫ অক্টোবর ২০২৬, আপডেট ০৬ অক্টোবর ২০২৬",
])
def test_incomplete_or_ambiguous_dates_are_not_guessed(raw):
    assert parse_card_date(raw) is None


def _quota_429(quota_id: str) -> httpx.Response:
    return httpx.Response(429, json={"error": {"code": 429, "status": "RESOURCE_EXHAUSTED", "details": [
        {"@type": "type.googleapis.com/google.rpc.QuotaFailure",
         "violations": [{"quotaId": quota_id, "quotaValue": "20"}]}]}})


async def test_daily_quota_429_stops_at_once_instead_of_spending_more_requests(monkeypatch):
    gemini = Gemini(_quota_429("GenerateRequestsPerDayPerProjectPerModel-FreeTier"), gemini_body())
    result = await extractor(gemini, monkeypatch).extract(IMAGE)
    assert len(gemini.requests) == 1 and result.status == STATUS_API_FAILED
    assert result.failure_message == API_FAILURE_MESSAGE
    assert [a["outcome"] for a in result.details["attempts"]] == ["quota_exhausted"]


async def test_per_minute_429_is_still_retried(monkeypatch):
    gemini = Gemini(_quota_429("GenerateRequestsPerMinutePerProjectPerModel-FreeTier"), gemini_body())
    result = await extractor(gemini, monkeypatch).extract(IMAGE)
    assert len(gemini.requests) == 2 and result.status == STATUS_SUCCEEDED


# ── several API keys: rotate when one reaches its limit ──────────────────

KEYS = ["key-one", "key-two", "key-three", "key-four", "key-five"]
MULTI = GeminiSettings(api_key=KEYS[0], api_keys=KEYS[1:], model_name="gemini-test", retry_base_delay_seconds=1.0)


def _used(gemini):
    return [r.headers["x-goog-api-key"] for r in gemini.requests]


def test_numbered_keys_are_read_in_order(monkeypatch):
    from app.core.config import _numbered_gemini_keys
    for name in ("GEMINI_API_KEY1", "GEMINI_API_KEY2", "GEMINI_API_KEY3", "GEMINI_API_KEY5", "GEMINI_API_KEY10"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("GEMINI_API_KEY10", "ten")
    monkeypatch.setenv("GEMINI_API_KEY2", "two")
    monkeypatch.setenv("GEMINI_API_KEY1", "one")
    keys = GeminiSettings(api_key="main", api_keys=_numbered_gemini_keys()).all_api_keys
    assert keys[:2] == ["main", "one"] and keys.index("two") < keys.index("ten")
    assert GeminiSettings(api_key="x", api_keys=["x", " ", "y"]).all_api_keys == ["x", "y"]  # no blanks/duplicates


async def test_a_key_out_of_quota_hands_the_next_call_to_the_next_key_at_once(monkeypatch):
    gemini = Gemini(_quota_429("GenerateRequestsPerDayPerProjectPerModel-FreeTier"), gemini_body())
    sleeps = Sleeps()
    result = await extractor(gemini, monkeypatch, settings=MULTI, sleep=sleeps).extract(IMAGE)
    assert result.status == STATUS_SUCCEEDED and result.attempts == 2
    assert _used(gemini) == ["key-one", "key-two"] and sleeps.calls == []  # no waiting for the switch
    assert [a["key"] for a in result.details["attempts"]] == [1, 2]
    assert not any(k in json.dumps(result.details) for k in KEYS)  # keys are never recorded


async def test_per_minute_limit_also_switches_key(monkeypatch):
    gemini = Gemini(_quota_429("GenerateRequestsPerMinutePerProjectPerModel-FreeTier"), gemini_body())
    result = await extractor(gemini, monkeypatch, settings=MULTI).extract(IMAGE)
    assert result.status == STATUS_SUCCEEDED and _used(gemini) == ["key-one", "key-two"]


async def test_keys_cycle_and_a_spent_key_stays_skipped_for_later_cards(monkeypatch):
    daily = lambda: _quota_429("GenerateRequestsPerDayPerProjectPerModel-FreeTier")
    gemini = Gemini(daily(), daily(), gemini_body())
    assert (await extractor(gemini, monkeypatch, settings=MULTI).extract(IMAGE)).status == STATUS_SUCCEEDED
    assert _used(gemini) == ["key-one", "key-two", "key-three"]
    # the next card starts on the key that worked, never on the spent ones
    gemini2 = Gemini(gemini_body())
    await extractor(gemini2, monkeypatch, settings=MULTI).extract(IMAGE)
    assert _used(gemini2) == ["key-three"]


async def test_other_errors_keep_the_9_request_rule_and_the_same_key(monkeypatch):
    gemini = Gemini(*[httpx.Response(503)] * 12)
    result = await extractor(gemini, monkeypatch, settings=MULTI).extract(IMAGE)
    assert len(gemini.requests) == 9 and result.status == STATUS_API_FAILED
    assert set(_used(gemini)) == {"key-one"}


async def test_rotation_never_exceeds_9_requests(monkeypatch):
    minute = lambda: _quota_429("GenerateRequestsPerMinutePerProjectPerModel-FreeTier")
    gemini = Gemini(*[minute() for _ in range(20)])
    result = await extractor(gemini, monkeypatch, settings=MULTI).extract(IMAGE)
    assert len(gemini.requests) == 9 and result.status == STATUS_API_FAILED
    assert _used(gemini)[:5] == KEYS  # every key tried in turn


async def test_when_every_key_is_out_of_daily_quota_it_stops_and_later_cards_make_no_call(monkeypatch):
    gemini = Gemini(*[_quota_429("GenerateRequestsPerDayPerProjectPerModel-FreeTier") for _ in range(9)])
    result = await extractor(gemini, monkeypatch, settings=MULTI).extract(IMAGE)
    assert _used(gemini) == KEYS and result.status == STATUS_API_FAILED  # 5 calls, not 9
    assert result.failure_message == API_FAILURE_MESSAGE
    later = Gemini(gemini_body())
    result = await extractor(later, monkeypatch, settings=MULTI).extract(IMAGE)
    assert later.requests == [] and result.status == STATUS_API_FAILED and result.details["skipped_reason"]
