"""Photo-card claim extraction - Gemini only, no OCR, no fallback.

    original image + active verified sources (with aliases)
        -> Gemini (<= 9 requests in 3 batches of 3, 10 s pause between batches)
        -> every request failed               -> API_FAILED       (verification never runs)
        -> success, but no usable headline    -> INVALID_CONTENT  (no retry, verification never runs)
        -> success with headline + source     -> SUCCEEDED (claimed-source verification)
        -> success with headline, but the
           outlet is missing, unrecognised
           or inactive                        -> SUCCEEDED (verified-sources verification;
                                                 the raw outlet text is kept as provenance only)

On success the extracted values ARE the claim: the headline is the claimed
text, the identified verified source is the claimed news outlet and the
printed date (when one is fully visible and parses) is the claimed
publication date. A missing or unparseable date is not a failure - the claim
simply has no date; nothing is defaulted or guessed.
"""

from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass, field
from datetime import date
from typing import Awaitable, Callable

import httpx
import structlog

from app.core.config import get_settings
from app.features.photocard.card_date import parse_card_date
from app.features.photocard.gemini_image_extractor import SourceOption, extract_with_gemini
from app.features.sources.models import VerifiedSource
from app.features.sources.repository import SourceRepository
from app.features.verification import source_policy

logger = structlog.get_logger(__name__)

MIN_HEADLINE_CHARS = 8
_LETTER_RE = re.compile(r"[^\W\d_]", re.UNICODE)
_MAX_CATALOGUE = 500

STATUS_PENDING = "PENDING"
STATUS_SUCCEEDED = "SUCCEEDED"
STATUS_API_FAILED = "API_FAILED"
STATUS_INVALID_CONTENT = "INVALID_CONTENT"

# User-facing reasons (also stored as the submission's failure_reason).
API_FAILURE_MESSAGE = (
    "Sorry for the temporary inconvenience. Information cannot be collected from the "
    "photo card right now. Please submit it again after a while."
)
INVALID_HEADLINE_MESSAGE = (
    "A valid headline could not be identified on the photo card. Please submit a photo "
    "card with a clear, readable headline."
)
INVALID_CONTENT_MESSAGE = (
    "A valid headline or a recognized news outlet could not be identified on the photo "
    "card. Please submit a photo card with a clear headline and the news outlet's name or logo."
)


@dataclass
class CardExtraction:
    status: str  # SUCCEEDED | API_FAILED | INVALID_CONTENT
    headline: str | None = None
    source: VerifiedSource | None = None
    # Why there is no usable source (SOURCE_NOT_DETECTED / SOURCE_UNRECOGNIZED /
    # SOURCE_INACTIVE) and the outlet text visible on the card, if any.
    source_reason: str | None = None
    raw_source_text: str | None = None
    published_date: date | None = None
    failure_code: str | None = None
    attempts: int = 0
    model_version: str | None = None
    details: dict = field(default_factory=dict)
    timings_ms: dict[str, int] = field(default_factory=dict)

    @property
    def succeeded(self) -> bool:
        return self.status == STATUS_SUCCEEDED

    @property
    def failure_message(self) -> str | None:
        if self.status == STATUS_API_FAILED:
            return API_FAILURE_MESSAGE
        if self.status == STATUS_INVALID_CONTENT:
            if self.failure_code == "headline_missing" and source_policy.fallback_enabled():
                return INVALID_HEADLINE_MESSAGE
            return INVALID_CONTENT_MESSAGE
        return None


def _usable_headline(raw: str | None) -> str | None:
    if raw is None:
        return None
    text = raw.strip()
    if len(text) < MIN_HEADLINE_CHARS or not _LETTER_RE.search(text):
        return None
    return text


class PhotocardClaimExtractor:

    def __init__(
        self,
        *,
        source_repo: SourceRepository,
        http_client: httpx.AsyncClient,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self.source_repo = source_repo
        self.http_client = http_client
        self._sleep = sleep

    async def extract(self, image_bytes: bytes) -> CardExtraction:
        settings = get_settings()
        active = [s for s in await self.source_repo.list_active(limit=_MAX_CATALOGUE) if s.is_active]
        by_canonical = {s.canonical_name: s for s in active}
        catalogue = [
            SourceOption(
                canonical_name=s.canonical_name,
                display_name=s.display_name,
                display_name_en=s.display_name_en,
                aliases=tuple(a for a in (s.aliases or []) if isinstance(a, str)),
            )
            for s in active
        ]

        started = time.perf_counter()
        gemini = await extract_with_gemini(
            image_bytes, sources=catalogue, http_client=self.http_client,
            settings=settings.gemini, sleep=self._sleep,
        )
        timings = {"gemini_extraction": int((time.perf_counter() - started) * 1000)}
        details: dict = {
            "model": gemini.model,
            "skipped_reason": gemini.skipped_reason,
            "attempts": [a.to_dict() for a in gemini.attempts],
            "catalogue_size": len(catalogue),
        }
        base = dict(attempts=len(gemini.attempts), model_version=gemini.model, details=details, timings_ms=timings)

        if not gemini.succeeded:
            details["failure_code"] = "gemini_unavailable"
            logger.warning("photocard_gemini_failed", attempts=len(gemini.attempts),
                           skipped_reason=gemini.skipped_reason,
                           outcomes=[a.outcome for a in gemini.attempts])
            return CardExtraction(status=STATUS_API_FAILED, failure_code="gemini_unavailable", **base)

        f = gemini.fields
        details["response"] = f.model_dump(mode="json")
        headline = _usable_headline(f.present("headline"))
        canonical = f.identified_source()
        # Only a source that is still active right now is accepted.
        source = by_canonical.get(canonical) if canonical else None
        source_reason = None
        if source is not None:
            fresh = await self.source_repo.get_by_canonical_name(source.canonical_name)
            if fresh is None or not fresh.is_active:
                source = None
                source_reason = source_policy.REASON_INACTIVE
        if source is None and source_reason is None:
            source_reason = (
                source_policy.REASON_NOT_DETECTED
                if f.source_status.value == "NOT_VISIBLE"
                else source_policy.REASON_UNRECOGNIZED
            )
        raw_source_text = (f.source_evidence or "").strip()[:255] or None
        details["source_reason"] = None if source is not None else source_reason

        if headline is not None and source is None and source_policy.fallback_enabled():
            # A readable headline is enough: the claim is checked against the
            # active verified sources. Nothing is guessed about the outlet.
            raw_date = f.present("date")
            published = parse_card_date(raw_date)
            details["date_parsed"] = published.isoformat() if published else None
            logger.info("photocard_source_fallback", reason=source_reason)
            return CardExtraction(
                status=STATUS_SUCCEEDED, headline=headline, source=None, published_date=published,
                source_reason=source_reason, raw_source_text=raw_source_text, **base,
            )

        if headline is None or source is None:
            code = "headline_missing" if headline is None else "source_not_identified"
            if headline is None and source is None:
                code = "headline_and_source_missing"
            details["failure_code"] = code
            logger.info("photocard_extraction_rejected", reason=code,
                        headline_status=f.headline_status.value, source_status=f.source_status.value)
            return CardExtraction(status=STATUS_INVALID_CONTENT, failure_code=code, **base)

        raw_date = f.present("date")
        published = parse_card_date(raw_date)
        details["date_parsed"] = published.isoformat() if published else None
        return CardExtraction(
            status=STATUS_SUCCEEDED, headline=headline, source=source, published_date=published,
            raw_source_text=raw_source_text, **base,
        )
