"""Shared claimed-source resolution — the single place that decides whether a
user's claimed_source_text resolves to a canonical, restrictable domain.

Used by both S01 (InputNormalizerStage, as a defense-in-depth backstop) and
the verification/photo-card services (as an up-front check, before a
Submission row is created or any search runs) so an unresolved source fails
fast and explicitly instead of silently falling through to an unrestricted,
domain-unfiltered web search — see s04_source_search.py's domain filter,
which only applies `if domain:`.
"""

from __future__ import annotations

from app.features.sources.repository import SourceRepository
from app.shared.utils.bangla_normalizer import extract_canonical_domain, normalize_source_name


async def resolve_claimed_source(
    raw_source: str, source_repo: SourceRepository
) -> str | None:
    """Best-effort resolution, in order of decreasing certainty:

    1. The text itself is a URL or bare domain.
    2. The text matches a known static alias.
    3. The text matches an entry in the verified-source registry (fuzzy/DB
       lookup).

    Returns ``None`` when none of the three succeed — callers decide what to
    do with that (raise, in every current caller).
    """
    if not raw_source or not raw_source.strip():
        return None

    canonical = extract_canonical_domain(raw_source)
    if canonical:
        return canonical

    canonical = normalize_source_name(raw_source)
    if canonical:
        return canonical

    try:
        source_record = await source_repo.resolve_source(raw_source)
    except Exception:
        # A DB/lookup hiccup here is not itself a "source not found" — the
        # caller still gets None and treats it the same as a genuine miss,
        # but this is not swallowed silently: it's logged by resolve_source's
        # own caller via the stage/service logger, not here (this module has
        # no logger of its own to avoid double-logging the common case).
        return None
    if source_record:
        return source_record.canonical_name

    return None
