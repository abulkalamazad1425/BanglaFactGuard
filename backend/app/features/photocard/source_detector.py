"""
Detect which verified news source a photo card claims to come from.

Almost every circulating photo card brands itself — an outlet logo, a wordmark
strip along the bottom, or a page URL. That branding *is* the claim's source
attribution, and recovering it removes the single most error-prone step from
the user's side of the flow.

Detection runs against the **raw** OCR text rather than the cleaned claim,
because branding is exactly what claim cleaning throws away.

Three matching strategies run in order of decreasing trust:

``domain``   a URL or bare domain in the text resolves to a source's canonical
             name. Unambiguous when present.
``exact``    a source name or alias appears verbatim in the normalised text.
``fuzzy``    a same-length window of the text is within an edit-distance
             threshold of a name or alias. This carries the detector: Bangla
             OCR routinely drops a matra or splits a conjunct, so
             "প্রথম আলো" comes back as "প্রথম আল৷" and exact matching alone
             would miss a perfectly legible banner.

Only **active** verified sources are considered — deactivated outlets must not
be selectable for verification (PDF §2.1).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import structlog
from Levenshtein import ratio as levenshtein_ratio

from app.features.photocard.claim_extractor import normalize_for_match as _normalise
from app.features.sources.models import VerifiedSource
from app.features.sources.repository import SourceRepository
from app.shared.utils.bangla_normalizer import extract_canonical_domain

logger = structlog.get_logger(__name__)

_URL_RE = re.compile(
    r"(?:https?://)?(?:www\.)?([a-z0-9][a-z0-9-]{1,62}(?:\.[a-z]{2,})+)",
    re.IGNORECASE,
)

# Aliases shorter than this produce runaway false positives against a page of
# OCR text ("rtv" would fire inside any three-letter garble).
_MIN_NEEDLE_CHARS = 4
# Cap the fuzzy search space; photo-card text is short, and scanning every
# window of a huge OCR dump would be wasteful.
_MAX_FUZZY_TEXT_CHARS = 4000


@dataclass
class DetectedSource:
    """A verified source the photo card appears to be attributed to."""

    source_id: str
    canonical_name: str
    display_name: str
    display_name_en: str | None
    confidence: float
    matched_text: str
    method: str


class SourceDetector:
    """Match photo-card branding against the verified-source registry."""

    def __init__(self, source_repo: SourceRepository) -> None:
        self.source_repo = source_repo

    async def detect(
        self,
        raw_text: str,
        *,
        threshold: float,
        limit: int = 5,
    ) -> list[DetectedSource]:
        """Return candidate sources, most confident first."""
        if not raw_text or not raw_text.strip():
            return []

        sources = await self._load_active_sources()
        if not sources:
            logger.warning("photocard_source_detection_no_active_sources")
            return []

        normalised_text = _normalise(raw_text)[:_MAX_FUZZY_TEXT_CHARS]
        domains = _extract_domains(raw_text)

        detections: dict[str, DetectedSource] = {}

        for source in sources:
            detection = self._match_source(
                source,
                normalised_text=normalised_text,
                domains=domains,
                threshold=threshold,
            )
            if detection is None:
                continue
            existing = detections.get(detection.canonical_name)
            if existing is None or detection.confidence > existing.confidence:
                detections[detection.canonical_name] = detection

        ranked = sorted(
            detections.values(), key=lambda item: item.confidence, reverse=True
        )
        logger.info(
            "photocard_source_detection_complete",
            candidates=len(ranked),
            top=ranked[0].canonical_name if ranked else None,
            top_confidence=round(ranked[0].confidence, 3) if ranked else None,
        )
        return ranked[:limit]

    async def _load_active_sources(self) -> list[VerifiedSource]:
        # The registry is small (tens of rows); one paged read per request is
        # cheaper than maintaining a cache that can go stale when an admin
        # deactivates a source mid-session.
        return await self.source_repo.list_active(limit=100, offset=0)

    def _match_source(
        self,
        source: VerifiedSource,
        *,
        normalised_text: str,
        domains: set[str],
        threshold: float,
    ) -> DetectedSource | None:
        if source.canonical_name.lower() in domains:
            return self._build(source, 1.0, source.canonical_name, "domain")

        base_domain = extract_canonical_domain(source.base_url or "")
        if base_domain and base_domain in domains:
            return self._build(source, 1.0, base_domain, "domain")

        best_score = 0.0
        best_needle = ""
        best_method = "fuzzy"

        for needle in self._needles(source):
            if needle in normalised_text:
                # Longer verbatim matches are stronger evidence than a short
                # alias that happens to be a substring.
                score = min(1.0, 0.94 + 0.01 * min(len(needle), 6))
                if score > best_score:
                    best_score, best_needle, best_method = score, needle, "exact"
                continue

            score, window = _best_window_ratio(normalised_text, needle)
            if score > best_score:
                best_score, best_needle, best_method = score, window, "fuzzy"

        if best_score < threshold:
            return None
        return self._build(source, best_score, best_needle, best_method)

    def _needles(self, source: VerifiedSource) -> list[str]:
        """Normalised search strings for one source, longest first."""
        candidates = [source.display_name, source.display_name_en, source.canonical_name]
        candidates.extend(source.aliases or [])

        seen: set[str] = set()
        needles: list[str] = []
        for candidate in candidates:
            if not candidate:
                continue
            normalised = _normalise(candidate)
            if len(normalised) < _MIN_NEEDLE_CHARS or normalised in seen:
                continue
            seen.add(normalised)
            needles.append(normalised)

        needles.sort(key=len, reverse=True)
        return needles

    @staticmethod
    def _build(
        source: VerifiedSource, confidence: float, matched_text: str, method: str
    ) -> DetectedSource:
        return DetectedSource(
            source_id=str(source.id),
            canonical_name=source.canonical_name,
            display_name=source.display_name,
            display_name_en=source.display_name_en,
            confidence=round(min(confidence, 1.0), 4),
            matched_text=matched_text,
            method=method,
        )


def _extract_domains(raw_text: str) -> set[str]:
    """Collect every domain mentioned in the card text."""
    domains: set[str] = set()
    for match in _URL_RE.finditer(raw_text):
        domain = extract_canonical_domain(match.group(1))
        if domain:
            domains.add(domain.lower())
    return domains


def _best_window_ratio(haystack: str, needle: str) -> tuple[float, str]:
    """Best Levenshtein ratio between ``needle`` and any window of ``haystack``.

    Windows are anchored to word starts rather than to every character offset:
    outlet names begin at a word boundary, and word-anchored scanning is an
    order of magnitude cheaper than a full sliding window.

    Each anchor is measured at several window lengths. A single fixed length
    is not enough — OCR both drops characters (a matra lost from a conjunct)
    and inserts them (a spurious space mid-word), so the true match region is
    sometimes shorter and sometimes longer than the name being searched for.
    Scoring only one length lets an adjacent word bleed into the window and
    depress an otherwise clean match below threshold.
    """
    if not haystack or not needle:
        return 0.0, ""

    span = len(needle)
    slack = max(2, span // 5)
    window_lengths = sorted({max(1, span - slack), span, span + slack})

    starts = [0]
    starts.extend(match.end() for match in re.finditer(r"\s", haystack))

    best_score = 0.0
    best_window = ""
    for start in starts:
        for window_len in window_lengths:
            window = haystack[start : start + window_len]
            if len(window) < span // 2:
                continue
            score = levenshtein_ratio(needle, window)
            if score > best_score:
                best_score = score
                best_window = window

    return best_score, best_window.strip()
