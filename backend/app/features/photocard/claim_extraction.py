"""Photo-card claim extraction: Gemini first, EasyOCR fallback.

    original image -> Gemini image extraction (<= 3 attempts in total)
                   -> on success: headline / date / source (raw)      [EasyOCR NOT run]
                   -> after the last failed attempt:
                        EasyOCR -> existing deterministic fallback extractor
                   -> nothing usable: an explicit extraction failure (no claim is fabricated)

The fallback never re-enters the Gemini loop. Extraction method, attempt
count, fallback use and per-attempt failure diagnostics are returned for
persistence (`ocr_extractions.extraction_details`).

Only the headline is verified. The extracted date and source are raw,
display-only metadata: verification always uses the user's own claimed
date and selected source.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Awaitable, Callable

import httpx
import structlog

from app.core.config import get_settings
from app.features.photocard.gemini_image_extractor import extract_with_gemini
from app.features.photocard.ocr_fallback_extractor import detect_date_text, extract_claim
from app.features.photocard.ocr_service import BanglaOcrService, OcrEngineUnavailableError, OcrFailedError, OcrOutput
from app.features.photocard.source_detector import SourceDetector
from app.features.sources.repository import SourceRepository

logger = structlog.get_logger(__name__)

METHOD_GEMINI = "GEMINI_IMAGE"
METHOD_OCR_FALLBACK = "OCR_FALLBACK"
MIN_HEADLINE_CHARS = 8


@dataclass
class PhotocardExtraction:
    headline: str
    date_text: str | None
    source_text: str | None
    method: str | None  # GEMINI_IMAGE | OCR_FALLBACK | None (nothing usable)
    gemini_attempts: int
    fallback_used: bool
    model_version: str | None = None
    warnings: list[str] = field(default_factory=list)
    diagnostics: dict = field(default_factory=dict)
    ocr_output: OcrOutput | None = None
    failure_reason: str | None = None
    timings_ms: dict[str, int] = field(default_factory=dict)

    @property
    def is_usable(self) -> bool:
        return self.method is not None and len(self.headline.strip()) >= MIN_HEADLINE_CHARS


class PhotocardClaimExtractor:

    def __init__(
        self,
        *,
        ocr_service: BanglaOcrService,
        source_repo: SourceRepository,
        http_client: httpx.AsyncClient,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self.ocr_service = ocr_service
        self.source_repo = source_repo
        self.http_client = http_client
        self._sleep = sleep

    async def extract(self, image_bytes: bytes) -> PhotocardExtraction:
        settings = get_settings()
        timings: dict[str, int] = {}

        started = time.perf_counter()
        gemini = await extract_with_gemini(
            image_bytes, http_client=self.http_client, settings=settings.gemini, sleep=self._sleep
        )
        timings["gemini_extraction"] = int((time.perf_counter() - started) * 1000)
        diagnostics: dict = {
            "gemini": {
                "model": gemini.model,
                "skipped_reason": gemini.skipped_reason,
                "attempts": [a.to_dict() for a in gemini.attempts],
            }
        }

        if gemini.succeeded:
            f = gemini.fields
            diagnostics["gemini"]["raw"] = f.model_dump(mode="json")
            return PhotocardExtraction(
                headline=f.present("headline").strip(),
                date_text=f.present("date"),
                source_text=f.present("source"),
                method=METHOD_GEMINI,
                gemini_attempts=len(gemini.attempts),
                fallback_used=False,
                model_version=gemini.model,
                diagnostics=diagnostics,
                timings_ms=timings,
            )

        logger.warning(
            "photocard_gemini_failed_using_ocr_fallback",
            attempts=len(gemini.attempts),
            skipped_reason=gemini.skipped_reason,
            outcomes=[a.outcome for a in gemini.attempts],
        )
        result = await self._ocr_fallback(image_bytes, diagnostics, timings)
        result.gemini_attempts = len(gemini.attempts)
        result.model_version = None
        return result

    async def _ocr_fallback(self, image_bytes: bytes, diagnostics: dict, timings: dict[str, int]) -> PhotocardExtraction:
        ocr_settings = get_settings().ocr

        def failed(reason: str, ocr: OcrOutput | None = None, warnings: list[str] | None = None) -> PhotocardExtraction:
            diagnostics["fallback"] = {**diagnostics.get("fallback", {}), "error": reason}
            return PhotocardExtraction(
                headline="", date_text=None, source_text=None, method=None, gemini_attempts=0,
                fallback_used=True, warnings=warnings or [], diagnostics=diagnostics, ocr_output=ocr,
                failure_reason=reason, timings_ms=timings,
            )

        started = time.perf_counter()
        try:
            ocr = await self.ocr_service.recognize(image_bytes)
        except OcrFailedError:
            timings["ocr"] = int((time.perf_counter() - started) * 1000)
            return failed("EasyOCR could not read any text from the image.")
        except OcrEngineUnavailableError as exc:
            timings["ocr"] = int((time.perf_counter() - started) * 1000)
            return failed(f"The OCR engine is unavailable: {exc.message}")
        timings["ocr"] = int((time.perf_counter() - started) * 1000)
        diagnostics["fallback"] = {"ocr_engine": f"{ocr.engine}:{ocr.variant}", "ocr_confidence": ocr.confidence}

        started = time.perf_counter()
        detections = await SourceDetector(self.source_repo).detect(ocr.text, threshold=ocr_settings.source_match_threshold)
        names = [n for d in detections for n in (d.display_name, d.display_name_en or "", d.canonical_name, d.matched_text) if n]
        lines = [(line.text, line.confidence) for line in ocr.lines]
        claim = extract_claim(
            lines,
            min_bangla_ratio=ocr_settings.min_line_bangla_ratio,
            min_confidence=ocr_settings.min_line_confidence,
            source_names=names,
        )
        timings["fallback_extraction"] = int((time.perf_counter() - started) * 1000)
        if len(claim.headline.strip()) < MIN_HEADLINE_CHARS:
            return failed("No readable headline could be extracted from the OCR text.", ocr, claim.warnings)
        return PhotocardExtraction(
            headline=claim.headline.strip(),
            date_text=detect_date_text(lines),
            source_text=detections[0].matched_text if detections else None,
            method=METHOD_OCR_FALLBACK,
            gemini_attempts=0,
            fallback_used=True,
            warnings=claim.warnings,
            diagnostics=diagnostics,
            ocr_output=ocr,
            timings_ms=timings,
        )
