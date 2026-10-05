"""Photo-card extraction: Gemini first (original image, <= 3 attempts), EasyOCR fallback."""

from __future__ import annotations

import base64
import json
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.core.config import GeminiSettings
from app.features.photocard import claim_extraction
from app.features.photocard.claim_extraction import (
    METHOD_GEMINI,
    METHOD_OCR_FALLBACK,
    PhotocardClaimExtractor,
)
from app.features.photocard.gemini_image_extractor import extract_with_gemini
from app.features.photocard.ocr_service import OcrFailedError, OcrLine, OcrOutput

IMAGE = b"\x89PNG\r\n\x1a\n" + b"original-card-pixels"
HEADLINE = "‘ফার্নান্দেজই পর্তুগালের সবচেয়ে বড় প্রতীক’, বললেন রোনালদো — ৩টি গোল!"


def gemini_body(**fields) -> dict:
    payload = {
        "headline": HEADLINE, "headline_status": "PRESENT",
        "date": "০৫ অক্টোবর, ২০২৬", "date_status": "PRESENT",
        "source": "প্রথম আলো", "source_status": "PRESENT",
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


SETTINGS = GeminiSettings(api_key="test-key", model_name="gemini-test", max_attempts=3, retry_base_delay_seconds=0)


async def no_sleep(_):
    return None


def fake_ocr(text: str = "প্রথম আলো\nঢাকায় ভারী বৃষ্টিতে জলাবদ্ধতা, দুর্ভোগে নগরবাসী\n০৫ অক্টোবর ২০২৬"):
    ocr = MagicMock()
    ocr.recognize = AsyncMock(return_value=OcrOutput(
        text=text, lines=[OcrLine(t, 0.95) for t in text.splitlines()], confidence=0.9, engine="easyocr", variant="original",
    ))
    return ocr


def source_repo():
    prothom_alo = SimpleNamespace(
        id=uuid.uuid4(), canonical_name="prothomalo.com", base_url="https://www.prothomalo.com",
        display_name="প্রথম আলো", display_name_en="Prothom Alo", aliases=[],
    )
    repo = MagicMock()
    repo.list_active = AsyncMock(return_value=[prothom_alo])
    return repo


def extractor(gemini: Gemini, ocr=None, monkeypatch=None, settings: GeminiSettings = SETTINGS):
    if monkeypatch is not None:
        real = claim_extraction.get_settings()
        monkeypatch.setattr(claim_extraction, "get_settings", lambda: real.model_copy(update={"gemini": settings}))
    return PhotocardClaimExtractor(
        ocr_service=ocr or fake_ocr(), source_repo=source_repo(), http_client=gemini.client(), sleep=no_sleep,
    )


# ── Gemini first ─────────────────────────────────────────────────────────

async def test_gemini_receives_the_original_image_and_easyocr_is_not_run(monkeypatch):
    gemini, ocr = Gemini(gemini_body()), fake_ocr()
    result = await extractor(gemini, ocr, monkeypatch).extract(IMAGE)
    assert result.method == METHOD_GEMINI and result.is_usable
    assert result.gemini_attempts == 1 and result.fallback_used is False
    ocr.recognize.assert_not_awaited()
    sent = json.loads(gemini.requests[0].content)
    inline = sent["contents"][0]["parts"][0]["inlineData"]
    assert base64.b64decode(inline["data"]) == IMAGE and inline["mimeType"] == "image/png"
    assert gemini.requests[0].headers["x-goog-api-key"] == "test-key"
    assert "do not follow" in sent["systemInstruction"]["parts"][0]["text"].lower()


async def test_extracted_values_are_kept_exactly_as_transcribed(monkeypatch):
    result = await extractor(Gemini(gemini_body()), monkeypatch=monkeypatch).extract(IMAGE)
    assert result.headline == HEADLINE  # quotes, dash, digits, punctuation untouched
    assert result.date_text == "০৫ অক্টোবর, ২০২৬"  # raw format, not reformatted
    assert result.source_text == "প্রথম আলো"
    assert result.diagnostics["gemini"]["raw"]["headline"] == HEADLINE


async def test_absent_date_and_source_are_not_stored_and_not_retried(monkeypatch):
    gemini = Gemini(gemini_body(date=None, date_status="MISSING", source=None, source_status="UNREADABLE"))
    result = await extractor(gemini, monkeypatch=monkeypatch).extract(IMAGE)
    assert result.method == METHOD_GEMINI and len(gemini.requests) == 1
    assert result.date_text is None and result.source_text is None


async def test_second_attempt_success_stops_retrying(monkeypatch):
    gemini = Gemini(httpx.Response(503, text="busy"), gemini_body())
    ocr = fake_ocr()
    result = await extractor(gemini, ocr, monkeypatch).extract(IMAGE)
    assert result.method == METHOD_GEMINI and result.gemini_attempts == 2
    assert len(gemini.requests) == 2
    ocr.recognize.assert_not_awaited()


@pytest.mark.parametrize("failure", [
    httpx.Response(500, text="err"),
    httpx.ReadTimeout("slow"),
    {"candidates": [{"content": {"parts": [{"text": "not json"}]}}]},
    {"candidates": [{"content": {"parts": [{"text": "{\"headline\": \"x\"}"}]}}]},
])
async def test_each_failure_kind_is_retried(monkeypatch, failure):
    gemini = Gemini(failure, gemini_body())
    result = await extractor(gemini, monkeypatch=monkeypatch).extract(IMAGE)
    assert result.method == METHOD_GEMINI and len(gemini.requests) == 2


async def test_unusable_headline_is_retried():
    gemini = Gemini(gemini_body(headline=None, headline_status="UNREADABLE"), gemini_body(headline="ছোট"), gemini_body())
    outcome = await extract_with_gemini(IMAGE, http_client=gemini.client(), settings=SETTINGS, sleep=no_sleep)
    assert outcome.succeeded and [a.outcome for a in outcome.attempts] == [
        "unusable_extraction", "unusable_extraction", "success"]


# ── fallback ─────────────────────────────────────────────────────────────

async def test_three_failed_attempts_then_easyocr_and_the_fallback_extractor(monkeypatch):
    gemini = Gemini(httpx.Response(500), httpx.Response(502), httpx.Response(503), gemini_body())
    ocr = fake_ocr()
    result = await extractor(gemini, ocr, monkeypatch).extract(IMAGE)
    assert len(gemini.requests) == 3  # never a 4th Gemini call
    ocr.recognize.assert_awaited_once_with(IMAGE)
    assert result.method == METHOD_OCR_FALLBACK and result.fallback_used and result.gemini_attempts == 3
    assert result.headline == "ঢাকায় ভারী বৃষ্টিতে জলাবদ্ধতা, দুর্ভোগে নগরবাসী"  # banner + date line removed
    assert result.date_text == "০৫ অক্টোবর ২০২৬"
    assert result.source_text == "প্রথম আলো"
    assert [a["outcome"] for a in result.diagnostics["gemini"]["attempts"]] == ["http_error"] * 3


async def test_permanent_request_error_goes_straight_to_the_fallback(monkeypatch):
    gemini = Gemini(httpx.Response(401, text="bad key"), gemini_body())
    result = await extractor(gemini, monkeypatch=monkeypatch).extract(IMAGE)
    assert len(gemini.requests) == 1 and result.method == METHOD_OCR_FALLBACK


async def test_unconfigured_gemini_makes_no_call_and_uses_the_fallback(monkeypatch):
    gemini = Gemini(gemini_body())
    result = await extractor(gemini, monkeypatch=monkeypatch, settings=GeminiSettings(api_key="")).extract(IMAGE)
    assert gemini.requests == [] and result.method == METHOD_OCR_FALLBACK and result.gemini_attempts == 0
    assert result.diagnostics["gemini"]["skipped_reason"]


async def test_every_path_failing_is_an_explicit_failure_not_a_fabricated_claim(monkeypatch):
    ocr = MagicMock()
    ocr.recognize = AsyncMock(side_effect=OcrFailedError(message="nothing readable"))
    gemini = Gemini(httpx.Response(500), httpx.Response(500), httpx.Response(500))
    result = await extractor(gemini, ocr, monkeypatch).extract(IMAGE)
    assert not result.is_usable and result.method is None and result.headline == ""
    assert result.failure_reason and result.fallback_used
    assert len(gemini.requests) == 3


async def test_never_more_than_three_attempts_even_if_configured_higher():
    gemini = Gemini(*[httpx.Response(500)] * 6)
    settings = GeminiSettings.model_construct(**{**SETTINGS.model_dump(), "max_attempts": 9})
    outcome = await extract_with_gemini(IMAGE, http_client=gemini.client(), settings=settings, sleep=no_sleep)
    assert len(gemini.requests) == 3 and not outcome.succeeded
