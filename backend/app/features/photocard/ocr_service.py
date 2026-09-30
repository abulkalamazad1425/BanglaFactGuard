"""
Bangla OCR for photo cards.

Two interchangeable engines sit behind one interface. Neither is imported at
module import time, so the application still starts when only one — or
neither — is installed; a missing engine surfaces as a 503 on the photo-card
endpoints instead of a boot failure.

The service does not trust a single pass. Each preprocessing variant produced
by :mod:`image_preprocessor` is recognised independently and the results are
scored by how much *Bangla* they actually contain, weighted by engine
confidence. Picking the winner this way is what makes recognition robust
across the very different card styles in circulation (flat-colour infographic,
photo background, dark theme).
"""

from __future__ import annotations

import asyncio
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

import structlog

from app.core.config import get_settings
from app.core.exceptions import BanglaFactGuardError
from app.features.photocard.image_preprocessor import ImageVariant, build_variants

logger = structlog.get_logger(__name__)
_SETTINGS = get_settings()

_OCR_POOL = ThreadPoolExecutor(
    max_workers=max(1, _SETTINGS.ocr.thread_workers),
    thread_name_prefix="photocard-ocr",
)

_BANGLA_CHAR_RE = re.compile(r"[ঀ-৿]")
_LETTER_RE = re.compile(r"[^\W\d_]", re.UNICODE)


class OcrEngineUnavailableError(BanglaFactGuardError):
    """No usable Bangla OCR engine is installed or configured."""

    http_status_code = 503


class OcrFailedError(BanglaFactGuardError):
    """The engine ran but produced no usable Bangla text."""

    http_status_code = 422


@dataclass
class OcrLine:
    """One recognised text line with the engine's confidence for it."""

    text: str
    confidence: float | None = None


@dataclass
class OcrOutput:
    """Result of the winning recognition pass."""

    text: str
    lines: list[OcrLine] = field(default_factory=list)
    confidence: float | None = None
    engine: str = "unknown"
    variant: str = "unknown"

    @property
    def bangla_char_count(self) -> int:
        return len(_BANGLA_CHAR_RE.findall(self.text))


def bangla_ratio(text: str) -> float:
    """Fraction of the letters in ``text`` that are Bangla.

    Digits and punctuation are excluded from the denominator: a Bangla line
    ending in ``2024`` or a bare ``।`` should not be penalised as non-Bangla.
    """
    letters = _LETTER_RE.findall(text)
    if not letters:
        return 0.0
    bangla = sum(1 for ch in letters if "ঀ" <= ch <= "৿")
    return bangla / len(letters)


class BanglaOcrService:
    """Engine-agnostic Bangla OCR with lazy, best-effort initialisation."""

    def __init__(self) -> None:
        self._engine_name: str | None = None
        self._easyocr_reader = None
        self._init_lock = asyncio.Lock()
        self._init_error: str | None = None

    @property
    def is_loaded(self) -> bool:
        return self._engine_name is not None

    @property
    def engine_name(self) -> str | None:
        return self._engine_name

    async def load(self) -> None:
        """Resolve and initialise an engine. Safe to call repeatedly."""
        if self._engine_name is not None:
            return

        async with self._init_lock:
            if self._engine_name is not None:
                return

            preferred = _SETTINGS.ocr.engine
            order = (
                ["tesseract", "easyocr"] if preferred == "auto" else [preferred]
            )

            failures: list[str] = []
            for candidate in order:
                try:
                    if candidate == "tesseract":
                        await asyncio.get_running_loop().run_in_executor(
                            _OCR_POOL, self._init_tesseract
                        )
                    else:
                        await asyncio.get_running_loop().run_in_executor(
                            _OCR_POOL, self._init_easyocr
                        )
                    self._engine_name = candidate
                    self._init_error = None
                    logger.info("photocard_ocr_engine_ready", engine=candidate)
                    return
                except Exception as exc:
                    failures.append(f"{candidate}: {exc}")
                    logger.warning(
                        "photocard_ocr_engine_unavailable",
                        engine=candidate,
                        error=str(exc),
                    )

            self._init_error = "; ".join(failures)
            raise OcrEngineUnavailableError(
                message=(
                    "No Bangla OCR engine is available. Install Tesseract with the "
                    "'ben' traineddata and `pip install pytesseract`, or "
                    "`pip install easyocr`. Set OCR_TESSERACT_CMD if the Tesseract "
                    "binary is not on PATH."
                ),
                details={"attempts": failures},
            )

    async def recognize(self, image_bytes: bytes) -> OcrOutput:
        """Recognise Bangla text, returning the best-scoring variant's output."""
        await self.load()

        loop = asyncio.get_running_loop()
        variants = await loop.run_in_executor(_OCR_POOL, build_variants, image_bytes)

        best: OcrOutput | None = None
        best_score = -1.0

        for variant in variants:
            try:
                output = await loop.run_in_executor(
                    _OCR_POOL, self._recognize_variant, variant
                )
            except Exception as exc:
                logger.warning(
                    "photocard_ocr_variant_failed",
                    variant=variant.name,
                    error=str(exc),
                )
                continue

            score = _score(output)
            logger.debug(
                "photocard_ocr_variant_scored",
                variant=variant.name,
                score=round(score, 2),
                bangla_chars=output.bangla_char_count,
                confidence=output.confidence,
            )
            if score > best_score:
                best_score = score
                best = output

        if best is None or not best.text.strip():
            raise OcrFailedError(
                message=(
                    "No text could be read from this image. Upload a sharper or "
                    "larger photo card."
                ),
                details={"engine": self._engine_name},
            )

        logger.info(
            "photocard_ocr_complete",
            engine=best.engine,
            variant=best.variant,
            line_count=len(best.lines),
            bangla_chars=best.bangla_char_count,
            confidence=best.confidence,
        )
        return best

    def _recognize_variant(self, variant: ImageVariant) -> OcrOutput:
        if self._engine_name == "tesseract":
            return self._run_tesseract(variant)
        return self._run_easyocr(variant)

    # ── Tesseract ────────────────────────────────────────────────────────

    def _init_tesseract(self) -> None:
        import pytesseract

        if _SETTINGS.ocr.tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = _SETTINGS.ocr.tesseract_cmd

        languages = pytesseract.get_languages(config="")
        required = _SETTINGS.ocr.tesseract_lang.split("+")[0]
        if required not in languages:
            raise RuntimeError(
                f"Tesseract is installed but the {required!r} traineddata is "
                f"missing (found: {sorted(languages)[:10]}…). Install the Bangla "
                f"language pack to enable photo-card OCR."
            )

    def _run_tesseract(self, variant: ImageVariant) -> OcrOutput:
        import pytesseract
        from pytesseract import Output

        best_output: OcrOutput | None = None
        best_score = -1.0

        for psm in _SETTINGS.ocr.tesseract_psm_modes:
            data = pytesseract.image_to_data(
                variant.image,
                lang=_SETTINGS.ocr.tesseract_lang,
                # OEM 1 = the LSTM engine; the legacy engine has no Bangla model.
                config=f"--oem 1 --psm {psm} -c preserve_interword_spaces=1",
                output_type=Output.DICT,
            )
            output = _tesseract_data_to_output(data, variant.name, psm)
            score = _score(output)
            if score > best_score:
                best_score = score
                best_output = output

        return best_output or OcrOutput(
            text="", engine="tesseract", variant=variant.name
        )

    # ── EasyOCR ──────────────────────────────────────────────────────────

    def _init_easyocr(self) -> None:
        import easyocr

        self._easyocr_reader = easyocr.Reader(
            _SETTINGS.ocr.easyocr_languages,
            gpu=_SETTINGS.ocr.easyocr_use_gpu,
            verbose=False,
        )

    def _run_easyocr(self, variant: ImageVariant) -> OcrOutput:
        import numpy as np

        if self._easyocr_reader is None:
            self._init_easyocr()

        # EasyOCR wants an array; the variants are already single-channel.
        array = np.asarray(variant.image.convert("RGB"))
        detections = self._easyocr_reader.readtext(array, detail=1, paragraph=False)
        return _easyocr_detections_to_output(detections, variant.name)


# ── Engine output normalisation ──────────────────────────────────────────


def _tesseract_data_to_output(data: dict, variant: str, psm: int) -> OcrOutput:
    """Group Tesseract's per-word rows back into visual lines."""
    grouped: dict[tuple[int, int, int, int], list[tuple[str, float]]] = {}

    for index, word in enumerate(data.get("text", [])):
        token = (word or "").strip()
        if not token:
            continue
        try:
            confidence = float(data["conf"][index])
        except (KeyError, ValueError, TypeError):
            confidence = -1.0
        # Tesseract reports -1 for structural rows that carry no recognition.
        if confidence < 0:
            continue

        key = (
            data["page_num"][index],
            data["block_num"][index],
            data["par_num"][index],
            data["line_num"][index],
        )
        grouped.setdefault(key, []).append((token, confidence / 100.0))

    lines: list[OcrLine] = []
    for key in sorted(grouped):
        words = grouped[key]
        text = " ".join(word for word, _ in words)
        confidences = [conf for _, conf in words]
        lines.append(
            OcrLine(text=text, confidence=sum(confidences) / len(confidences))
        )

    return _build_output(lines, engine="tesseract", variant=f"{variant}/psm{psm}")


def _easyocr_detections_to_output(detections: list, variant: str) -> OcrOutput:
    """Group EasyOCR's per-box detections into visual lines.

    EasyOCR returns independent boxes with no line structure, so boxes are
    bucketed by vertical overlap and then ordered left-to-right within each
    bucket — which is what reconstructs a multi-column card correctly.
    """
    boxes: list[tuple[float, float, float, str, float]] = []
    for detection in detections:
        try:
            polygon, text, confidence = detection[0], detection[1], detection[2]
        except (IndexError, TypeError):
            continue
        token = (text or "").strip()
        if not token:
            continue
        ys = [float(point[1]) for point in polygon]
        xs = [float(point[0]) for point in polygon]
        boxes.append((min(ys), max(ys), min(xs), token, float(confidence)))

    boxes.sort(key=lambda box: (box[0], box[2]))

    lines: list[OcrLine] = []
    current: list[tuple[float, str, float]] = []
    current_bottom = -1.0
    current_height = 0.0

    for top, bottom, left, token, confidence in boxes:
        height = max(bottom - top, 1.0)
        # Same line when this box starts before the previous one has ended,
        # allowing half a glyph height of slack for baseline jitter.
        if current and top < current_bottom - 0.5 * min(height, current_height):
            current.append((left, token, confidence))
            current_bottom = max(current_bottom, bottom)
            current_height = max(current_height, height)
            continue

        if current:
            lines.append(_flush_easyocr_line(current))
        current = [(left, token, confidence)]
        current_bottom = bottom
        current_height = height

    if current:
        lines.append(_flush_easyocr_line(current))

    return _build_output(lines, engine="easyocr", variant=variant)


def _flush_easyocr_line(parts: list[tuple[float, str, float]]) -> OcrLine:
    parts.sort(key=lambda part: part[0])
    text = " ".join(token for _, token, _ in parts)
    confidences = [confidence for _, _, confidence in parts]
    return OcrLine(text=text, confidence=sum(confidences) / len(confidences))


def _build_output(lines: list[OcrLine], *, engine: str, variant: str) -> OcrOutput:
    kept = [line for line in lines if line.text.strip()]
    text = "\n".join(line.text for line in kept)
    confidences = [
        line.confidence for line in kept if line.confidence is not None
    ]
    return OcrOutput(
        text=text,
        lines=kept,
        confidence=(sum(confidences) / len(confidences)) if confidences else None,
        engine=engine,
        variant=variant,
    )


def _score(output: OcrOutput) -> float:
    """Rank a recognition pass by recovered Bangla, weighted by confidence.

    Character count alone would favour passes that hallucinate long strings of
    garbage; confidence alone would favour passes that read three clean words
    and miss the headline. The product balances both.
    """
    bangla_chars = output.bangla_char_count
    if bangla_chars == 0:
        return 0.0
    confidence = output.confidence if output.confidence is not None else 0.5
    return bangla_chars * (0.5 + 0.5 * confidence) * bangla_ratio(output.text)
