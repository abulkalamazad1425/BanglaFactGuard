"""
tests/unit/test_gemini_extractor.py
=====================================
Unattended photo-card headline extraction: Gemini first, deterministic
fallback (claim_extractor.extract_claim) always available. Covers the
decision logic in app/features/photocard/gemini_extractor.py — the actual
HTTP call to Gemini is mocked throughout; nothing here makes a real network
call or requires a real API key.

Covers:
- Grounding check: a headline must share enough words with the OCR text it
  was extracted from, or it's treated as ungrounded (the mechanical defense
  against hallucination and prompt injection embedded in OCR'd text).
- extract_headline() falls back to the deterministic extractor when Gemini
  is unconfigured, the HTTP call fails, the response is malformed, the
  headline is empty, or the headline fails the grounding check — and never
  raises in any of those cases.
- extract_headline() uses Gemini's result when it's valid and grounded.
"""

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.core.config import GeminiSettings
from app.features.photocard.gemini_extractor import (
    GeminiCallError,
    _call_gemini,
    _passes_grounding_check,
    extract_headline,
)


# ─── _passes_grounding_check ─────────────────────────────────────────────


def test_grounded_headline_passes():
    ocr_text = "প্রধানমন্ত্রী শেখ হাসিনা আজ ঢাকায় নতুন হাসপাতাল উদ্বোধন করেছেন।"
    headline = "প্রধানমন্ত্রী শেখ হাসিনা নতুন হাসপাতাল উদ্বোধন করেছেন"
    assert _passes_grounding_check(headline, ocr_text, min_overlap=0.5) is True


def test_ungrounded_headline_fails():
    ocr_text = "প্রধানমন্ত্রী শেখ হাসিনা আজ ঢাকায় নতুন হাসপাতাল উদ্বোধন করেছেন।"
    headline = "সম্পূর্ণ ভিন্ন একটি বিষয়ে সম্পূর্ণ অসম্পর্কিত বাক্য"
    assert _passes_grounding_check(headline, ocr_text, min_overlap=0.5) is False


def test_empty_headline_fails_grounding():
    assert _passes_grounding_check("", "কিছু টেক্সট", min_overlap=0.5) is False


# ─── _call_gemini ─────────────────────────────────────────────────────────


def _settings(**overrides) -> GeminiSettings:
    base = dict(
        api_key="test-key",
        model_name="gemini-2.0-flash",
        base_url="https://example.invalid/v1beta",
        timeout_seconds=5,
        min_grounding_overlap=0.5,
    )
    base.update(overrides)
    return GeminiSettings(**base)


def _gemini_http_response(status_code: int, json_body: dict | None = None, text: str = ""):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json = MagicMock(return_value=json_body or {})
    resp.text = text
    return resp


@pytest.mark.asyncio
async def test_call_gemini_raises_on_http_error_status():
    http_client = AsyncMock()
    http_client.post = AsyncMock(
        return_value=_gemini_http_response(403, text="forbidden")
    )
    with pytest.raises(GeminiCallError):
        await _call_gemini("ocr text", http_client=http_client, settings=_settings())
    http_client.post.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [403, 404])
async def test_call_gemini_does_not_retry_non_retryable_status(status_code):
    http_client = AsyncMock()
    http_client.post = AsyncMock(
        return_value=_gemini_http_response(status_code, text="client error")
    )

    with pytest.raises(GeminiCallError):
        await _call_gemini("ocr text", http_client=http_client, settings=_settings())

    http_client.post.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [429, 500, 502, 503, 504])
async def test_call_gemini_retries_retryable_status_three_total_attempts(
    monkeypatch, status_code
):
    sleep = AsyncMock()
    monkeypatch.setattr("app.features.photocard.gemini_extractor.asyncio.sleep", sleep)
    http_client = AsyncMock()
    http_client.post = AsyncMock(
        return_value=_gemini_http_response(status_code, text="transient error")
    )

    with pytest.raises(GeminiCallError):
        await _call_gemini("ocr text", http_client=http_client, settings=_settings())

    assert http_client.post.await_count == 3
    assert sleep.await_count == 2


@pytest.mark.asyncio
async def test_call_gemini_returns_success_after_retry(monkeypatch):
    import json

    sleep = AsyncMock()
    monkeypatch.setattr("app.features.photocard.gemini_extractor.asyncio.sleep", sleep)
    payload = {"headline": "retry succeeded"}
    success_body = {
        "candidates": [{"content": {"parts": [{"text": json.dumps(payload)}]}}]
    }
    http_client = AsyncMock()
    http_client.post = AsyncMock(
        side_effect=[
            _gemini_http_response(503, text="unavailable"),
            _gemini_http_response(200, success_body),
        ]
    )

    result = await _call_gemini(
        "ocr text", http_client=http_client, settings=_settings()
    )

    assert result == payload
    assert http_client.post.await_count == 2
    sleep.assert_awaited_once_with(1.0)


@pytest.mark.asyncio
async def test_call_gemini_raises_on_network_error():
    http_client = AsyncMock()
    http_client.post = AsyncMock(side_effect=httpx.ConnectTimeout("timed out"))
    with pytest.raises(GeminiCallError):
        await _call_gemini("ocr text", http_client=http_client, settings=_settings())
    http_client.post.assert_awaited_once()


@pytest.mark.asyncio
async def test_call_gemini_raises_on_malformed_response_shape():
    http_client = AsyncMock()
    http_client.post = AsyncMock(
        return_value=_gemini_http_response(200, {"unexpected": "shape"})
    )
    with pytest.raises(GeminiCallError):
        await _call_gemini("ocr text", http_client=http_client, settings=_settings())


@pytest.mark.asyncio
async def test_call_gemini_raises_on_non_json_inner_text():
    inner_part = {"text": "not valid json {{{"}
    body = {"candidates": [{"content": {"parts": [inner_part]}}]}
    http_client = AsyncMock()
    http_client.post = AsyncMock(return_value=_gemini_http_response(200, body))
    with pytest.raises(GeminiCallError):
        await _call_gemini("ocr text", http_client=http_client, settings=_settings())


@pytest.mark.asyncio
async def test_call_gemini_raises_when_headline_field_missing():
    import json

    body = {
        "candidates": [
            {"content": {"parts": [{"text": json.dumps({"detected_source_text": None})}]}}
        ]
    }
    http_client = AsyncMock()
    http_client.post = AsyncMock(return_value=_gemini_http_response(200, body))
    with pytest.raises(GeminiCallError):
        await _call_gemini("ocr text", http_client=http_client, settings=_settings())


@pytest.mark.asyncio
async def test_call_gemini_returns_parsed_dict_on_success():
    import json

    payload = {
        "headline": "প্রধানমন্ত্রী নতুন হাসপাতাল উদ্বোধন করেছেন",
        "detected_source_text": "প্রথম আলো",
        "detected_date_text": None,
        "extraction_warnings": [],
    }
    body = {"candidates": [{"content": {"parts": [{"text": json.dumps(payload)}]}}]}
    http_client = AsyncMock()
    http_client.post = AsyncMock(return_value=_gemini_http_response(200, body))

    result = await _call_gemini("ocr text", http_client=http_client, settings=_settings())
    assert result["headline"] == payload["headline"]
    assert result["detected_source_text"] == "প্রথম আলো"


# ─── extract_headline — fallback orchestration ──────────────────────────


_OCR_TEXT = "প্রধানমন্ত্রী শেখ হাসিনা আজ ঢাকায় নতুন হাসপাতাল উদ্বোধন করেছেন।"
_RAW_LINES = [(_OCR_TEXT, 0.9)]


@pytest.mark.asyncio
async def test_falls_back_when_gemini_not_configured(monkeypatch):
    unconfigured = _settings(api_key="")
    monkeypatch.setattr(
        "app.features.photocard.gemini_extractor.get_settings",
        lambda: MagicMock(gemini=unconfigured),
    )
    http_client = AsyncMock()

    result = await extract_headline(
        _OCR_TEXT,
        raw_lines=_RAW_LINES,
        source_names=None,
        http_client=http_client,
        min_bangla_ratio=0.45,
        min_confidence=0.30,
    )

    assert result.extractor_used == "EXISTING_FALLBACK"
    http_client.post.assert_not_called()


@pytest.mark.asyncio
async def test_falls_back_when_gemini_call_fails(monkeypatch):
    configured = _settings()
    monkeypatch.setattr(
        "app.features.photocard.gemini_extractor.get_settings",
        lambda: MagicMock(gemini=configured),
    )
    monkeypatch.setattr(
        "app.features.photocard.gemini_extractor._call_gemini",
        AsyncMock(side_effect=GeminiCallError("boom")),
    )

    result = await extract_headline(
        _OCR_TEXT,
        raw_lines=_RAW_LINES,
        source_names=None,
        http_client=AsyncMock(),
        min_bangla_ratio=0.45,
        min_confidence=0.30,
    )

    assert result.extractor_used == "EXISTING_FALLBACK"


@pytest.mark.asyncio
async def test_falls_back_when_gemini_headline_empty(monkeypatch):
    configured = _settings()
    monkeypatch.setattr(
        "app.features.photocard.gemini_extractor.get_settings",
        lambda: MagicMock(gemini=configured),
    )
    monkeypatch.setattr(
        "app.features.photocard.gemini_extractor._call_gemini",
        AsyncMock(return_value={"headline": "   "}),
    )

    result = await extract_headline(
        _OCR_TEXT,
        raw_lines=_RAW_LINES,
        source_names=None,
        http_client=AsyncMock(),
        min_bangla_ratio=0.45,
        min_confidence=0.30,
    )

    assert result.extractor_used == "EXISTING_FALLBACK"


@pytest.mark.asyncio
async def test_falls_back_when_gemini_headline_ungrounded(monkeypatch):
    configured = _settings()
    monkeypatch.setattr(
        "app.features.photocard.gemini_extractor.get_settings",
        lambda: MagicMock(gemini=configured),
    )
    monkeypatch.setattr(
        "app.features.photocard.gemini_extractor._call_gemini",
        AsyncMock(
            return_value={"headline": "সম্পূর্ণ ভিন্ন একটি অসম্পর্কিত বাক্য একেবারেই"}
        ),
    )

    result = await extract_headline(
        _OCR_TEXT,
        raw_lines=_RAW_LINES,
        source_names=None,
        http_client=AsyncMock(),
        min_bangla_ratio=0.45,
        min_confidence=0.30,
    )

    assert result.extractor_used == "EXISTING_FALLBACK"


@pytest.mark.asyncio
async def test_uses_gemini_result_when_valid_and_grounded(monkeypatch):
    configured = _settings()
    monkeypatch.setattr(
        "app.features.photocard.gemini_extractor.get_settings",
        lambda: MagicMock(gemini=configured),
    )
    monkeypatch.setattr(
        "app.features.photocard.gemini_extractor._call_gemini",
        AsyncMock(
            return_value={
                "headline": "প্রধানমন্ত্রী শেখ হাসিনা নতুন হাসপাতাল উদ্বোধন করেছেন",
                "detected_source_text": "প্রথম আলো",
                "detected_date_text": "১৫ মার্চ",
                "extraction_warnings": ["minor OCR noise"],
            }
        ),
    )

    result = await extract_headline(
        _OCR_TEXT,
        raw_lines=_RAW_LINES,
        source_names=None,
        http_client=AsyncMock(),
        min_bangla_ratio=0.45,
        min_confidence=0.30,
    )

    assert result.extractor_used == "GEMINI"
    assert result.model_version == "gemini-2.0-flash"
    assert result.detected_source_text == "প্রথম আলো"
    assert result.detected_date_text == "১৫ মার্চ"
    assert "minor OCR noise" in result.warnings
    assert result.is_usable is True
