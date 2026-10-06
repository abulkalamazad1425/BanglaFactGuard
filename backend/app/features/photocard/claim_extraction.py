"""Photo-card claim extraction - Gemini only, no OCR, no fallback.

    original image + active verified sources (with aliases)
        -> Gemini (<= 9 requests in 3 batches of 3, 10 s pause between batches)
        -> every request failed               -> API_FAILED       (verification never runs)
        -> success, but no headline or no
           active verified source identified  -> INVALID_CONTENT  (no retry, verification never runs)
        -> success with headline + source     -> SUCCEEDED

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
INVALID_CONTENT_MESSAGE = (
    "A valid headline or a recognized news outlet could not be identified on the photo "
    "card. Please submit a photo card with a clear headline and the news outlet's name or logo."
)


@dataclass
class CardExtraction:
    status: str  # SUCCEEDED | API_FAILED | INVALID_CONTENT
    headline: str | None = None
    source: VerifiedSource | None = None
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
        if source is not None:
            fresh = await self.source_repo.get_by_canonical_name(source.canonical_name)
            if fresh is None or not fresh.is_active:
                source = None

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
            status=STATUS_SUCCEEDED, headline=headline, source=source, published_date=published, **base,
        )
