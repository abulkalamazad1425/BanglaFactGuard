from __future__ import annotations

from app.features.sources.repository import SourceRepository
from app.shared.utils.bangla_normalizer import extract_canonical_domain, normalize_source_name


async def resolve_claimed_source(
    raw_source: str, source_repo: SourceRepository
) -> str | None:
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
        return None
    if source_record:
        return source_record.canonical_name

    return None
