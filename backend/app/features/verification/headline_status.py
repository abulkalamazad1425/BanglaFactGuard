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
