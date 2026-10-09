"""The one source-resolution policy shared by registration, the photo-card
flow and the pipeline (S01), so the same input never gets a different
verification mode in different places.

Two explicit modes:

* ``CLAIMED_SOURCE`` - the claim names an outlet that resolves (and is not a
  deactivated verified source). Unchanged behaviour: search and fetch are
  restricted to that one outlet, with Google and its internal search.
* ``VERIFIED_SOURCES`` - no outlet was given, or it is not recognised, or it
  is a deactivated verified source. Google only, restricted to the domains of
  the currently ACTIVE verified sources; the internal-site provider is never
  used. An unknown outlet is never guessed to be a verified publisher.

Identity: a claimed-source claim keeps exactly the hash it always had. A
verified-sources claim hashes a ``verified-sources:<fingerprint>`` key in the
source slot, where the fingerprint covers the active publishers and their
domains, so a registry change starts a new verification context instead of
relabelling an old result.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

from app.core.config import get_settings
from app.features.sources.repository import SourceRepository
from app.features.sources.resolution import resolve_claimed_source
from app.shared.utils.bangla_normalizer import extract_canonical_domain

CLAIMED_SOURCE = "CLAIMED_SOURCE"
VERIFIED_SOURCES = "VERIFIED_SOURCES"

# Why a claim is verified the way it is (persisted with the result).
REASON_SELECTED = "SOURCE_SELECTED"
REASON_DETECTED = "SOURCE_DETECTED"
REASON_NOT_SUPPLIED = "SOURCE_NOT_SUPPLIED"
REASON_NOT_DETECTED = "SOURCE_NOT_DETECTED"
REASON_UNRECOGNIZED = "SOURCE_UNRECOGNIZED"
REASON_INACTIVE = "SOURCE_INACTIVE"

_VERIFIED_KEY_PREFIX = "verified-sources:"
_MAX_PUBLISHERS = 500


def fallback_enabled() -> bool:
    return get_settings().search.verified_source_fallback_enabled


@dataclass(frozen=True)
class SourceResolution:
    mode: str
    canonical: str | None
    reason: str
    raw_text: str | None = None

    @property
    def is_fallback(self) -> bool:
        return self.mode == VERIFIED_SOURCES


@dataclass
class VerifiedPublisher:
    canonical: str
    name: str
    domains: list[str]
    config: dict

    def to_summary(self) -> dict:
        return {"canonical": self.canonical, "name": self.name, "domains": list(self.domains)}


@dataclass
class VerifiedScope:
    publishers: list[VerifiedPublisher] = field(default_factory=list)
    fingerprint: str = ""

    @property
    def empty(self) -> bool:
        return not self.publishers

    @property
    def all_domains(self) -> list[str]:
        out: list[str] = []
        for p in self.publishers:
            for d in p.domains:
                if d not in out:
                    out.append(d)
        return out

    def publisher_for_host(self, host: str) -> VerifiedPublisher | None:
        from app.shared.utils.domains import is_allowed_host

        for p in self.publishers:
            if is_allowed_host(host, p.domains):
                return p
        return None

    def publisher_for_url(self, url: str) -> VerifiedPublisher | None:
        from urllib.parse import urlparse

        try:
            host = urlparse(url).hostname or ""
        except ValueError:
            return None
        return self.publisher_for_host(host)


def source_config_for(record) -> dict:
    """The per-outlet configuration S04-S06 use (selectors, allowed hosts)."""
    return {
        "name": record.display_name,
        "body_selectors": record.body_selectors or [],
        "title_selectors": record.title_selectors or [],
        "date_selectors": record.date_selectors or [],
        "internal_search_url": record.internal_search_url,
        "article_url_patterns": record.article_url_patterns or [],
        # Registered channels for this outlet: S04 filters candidate hosts and
        # S05 validates FINAL redirected hosts against them.
        "allowed_domains": [
            d
            for d in (
                extract_canonical_domain(record.base_url or ""),
                *(extract_canonical_domain(str(a)) for a in (record.aliases or [])),
            )
            if d
        ],
    }


async def resolve_source(
    raw_text: str | None,
    source_repo: SourceRepository,
    *,
    selected_reason: str = REASON_SELECTED,
    missing_reason: str = REASON_NOT_SUPPLIED,
) -> SourceResolution:
    """Decide the verification mode for a claimed source text."""
    raw = (raw_text or "").strip() or None
    if raw is None:
        return SourceResolution(VERIFIED_SOURCES, None, missing_reason, None)
    canonical = await resolve_claimed_source(raw, source_repo)
    if canonical is None:
        return SourceResolution(VERIFIED_SOURCES, None, REASON_UNRECOGNIZED, raw)
    try:
        record = await source_repo.get_by_canonical_name(canonical)
    except Exception:  # noqa: BLE001 - a lookup hiccup keeps the claimed path
        record = None
    if record is not None and not record.is_active:
        return SourceResolution(VERIFIED_SOURCES, None, REASON_INACTIVE, raw)
    return SourceResolution(CLAIMED_SOURCE, canonical, selected_reason, raw)


async def load_verified_scope(source_repo: SourceRepository) -> VerifiedScope:
    """Active verified publishers with their allowed domains and selectors.
    An empty registry is an empty scope - never an unrestricted search."""
    records = [s for s in await source_repo.list_active(limit=_MAX_PUBLISHERS) if s.is_active]
    publishers: list[VerifiedPublisher] = []
    for r in records:
        config = source_config_for(r)
        domains: list[str] = []
        for d in [extract_canonical_domain(r.canonical_name) or r.canonical_name, *config["allowed_domains"]]:
            d = (d or "").strip().lower()
            if d.startswith("www."):
                d = d[4:]
            if d and d not in domains:
                domains.append(d)
        publishers.append(VerifiedPublisher(r.canonical_name, r.display_name, domains, config))
    publishers.sort(key=lambda p: p.canonical)
    payload = [[p.canonical, sorted(p.domains)] for p in publishers]
    fingerprint = hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()[:24]
    return VerifiedScope(publishers=publishers, fingerprint=fingerprint)


def verified_identity_key(scope: VerifiedScope) -> str:
    """Stands in for the canonical source in the claim identity."""
    return f"{_VERIFIED_KEY_PREFIX}{scope.fingerprint or 'empty'}"


def is_verified_identity_key(value: str | None) -> bool:
    return bool(value) and value.startswith(_VERIFIED_KEY_PREFIX)
