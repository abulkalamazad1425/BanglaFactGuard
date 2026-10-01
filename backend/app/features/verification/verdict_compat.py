"""Bridge between the AI pipeline's 3-dimensional verdict and expert review.

Expert review is a credibility-weighted consensus vote that predates and is
independent of the (source_status, content_status, date_status) model: experts
cast a single categorical vote, and the AI's own "vote" in that consensus has
always been a single category too (see ExpertReviewService._finalize_submission).
Redesigning that voting/credibility-scoring system around three independent
axes is a distinct, unspecified problem — nothing in this change asks for it.

This module is the seam: a pure, deterministic projection of the pipeline's
real verdict onto the legacy single-category shape, used ONLY to feed the
existing expert-consensus mechanism and its "AI verdict" display in the
expert queue. It is never returned as "the verdict" from the verification API
— see VerificationResponse, which exposes source_status/content_status/
date_status directly and does not collapse them.
"""

from __future__ import annotations

from app.core.config import get_settings
from app.core.constants import ContentStatus, DateStatus, ExpertVerdict, SourceStatus


def derive_expert_verdict(
    source_status: SourceStatus | None,
    content_status: ContentStatus | None,
    *,
    contradiction_score: float | None = None,
) -> ExpertVerdict:
    if source_status != SourceStatus.CONFIRMED:
        return ExpertVerdict.NOT_FOUND_IN_CLAIMED_SOURCE

    if content_status == ContentStatus.MATCHED:
        return ExpertVerdict.TRUE

    # ALTERED (or unknown, treated conservatively as altered): outright
    # contradiction maps to FALSE, milder alteration (e.g. a manipulation
    # flag without a strong contradiction signal) maps to PARTIALLY_TRUE —
    # mirroring the distinction the pre-existing voting system already
    # depends on for its "matched"/credibility-accuracy bookkeeping.
    threshold = get_settings().classification.contradiction_override_threshold
    if (contradiction_score or 0.0) > threshold:
        return ExpertVerdict.FALSE
    return ExpertVerdict.PARTIALLY_TRUE


def format_verdict_display(
    source_status: SourceStatus | None,
    content_status: ContentStatus | None,
    date_status: DateStatus | None = None,
) -> str | None:
    """Human-readable one-line summary for the expert queue's "AI said" column."""
    if source_status is None:
        return None
    if source_status == SourceStatus.NOT_FOUND:
        return "Source: NOT FOUND"

    parts = [f"Source: {source_status.value}"]
    if content_status is not None:
        parts.append(f"Content: {content_status.value}")
    if date_status is not None:
        parts.append(f"Date: {date_status.value}")
    return " · ".join(parts)
