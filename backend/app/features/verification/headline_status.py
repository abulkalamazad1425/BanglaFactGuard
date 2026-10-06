"""Headline Alteration display status: Exact Matched / Meaning Preserved / Altered.

Only the stored MATCHED verdict is split; nothing is re-compared and the
ALTERED determination is passed through untouched, so an altered headline can
never become Meaning Preserved here.

Exactness comes from evidence, in this order:
1. `verification_results.headline_exact_match` — written by S13 from the
   comparator's own exact-match shortcut (`is_exact_match`).
2. The stored Headline Alteration detail's `basis == "exact"`.
3. For an older MATCHED row with neither, the stored claim headline and
   source title are re-checked with the same `is_exact_match` normalisation
   (NFC, zero-width characters removed, whitespace collapsed, one trailing
   ।.!? removed — nothing else). Semantic similarity never counts.
Without enough evidence a MATCHED row is shown as Meaning Preserved, never
promoted to Exact Matched.
"""

from __future__ import annotations

from app.core.constants import ContentStatus, HeadlineAlterationStatus
from app.features.verification.analysis.headline_comparison import is_exact_match


def derive_headline_status(
    content_status: ContentStatus | str | None,
    *,
    exact_match: bool | None = None,
    basis: str | None = None,
    claim_headline: str | None = None,
    source_title: str | None = None,
) -> HeadlineAlterationStatus | None:
    value = getattr(content_status, "value", content_status)
    if value == ContentStatus.ALTERED.value:
        return HeadlineAlterationStatus.ALTERED
    if value != ContentStatus.MATCHED.value:
        return None
    if exact_match is True or basis == "exact":
        return HeadlineAlterationStatus.EXACT_MATCHED
    if exact_match is None and claim_headline and source_title and is_exact_match(claim_headline, source_title):
        return HeadlineAlterationStatus.EXACT_MATCHED
    return HeadlineAlterationStatus.MEANING_PRESERVED


def headline_status_for_result(result, *, claim_headline: str | None = None) -> HeadlineAlterationStatus | None:
    """The display status for a stored VerificationResult (AI preliminary
    finding). Legacy rows (no headline_check_status) have no headline verdict."""
    from app.features.verification.presenter import is_headline_result, parse_analysis

    if result is None or not is_headline_result(result):
        return None
    detail = None
    analysis = parse_analysis(result.analysis_details)
    if analysis is not None:
        detail = analysis.headline_alteration
    return derive_headline_status(
        result.content_status,
        exact_match=result.headline_exact_match,
        basis=detail.basis if detail else None,
        claim_headline=(detail.claim_headline if detail else None) or claim_headline,
        source_title=detail.source_title if detail else None,
    )
