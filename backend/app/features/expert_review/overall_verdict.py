"""AI-implied Overall verdict — used only as the AI's weighted prior in the
expert Overall tally (see ExpertReviewService._finalize_submission) and for
display ("AI preliminary: implied REAL") before expert review completes.

This is a pure presentation/weighting derivation, not a pipeline component:
it reads already-persisted fields and does not influence, and is never
written back into, the AI pipeline's own (source_status, content_status,
date_status) classification (s11_classifier.py) or the multimodal inference
engine. Experts still cast their own independent Overall vote; this is only
what the AI's existing output implies, for weighting and display purposes.
"""

from __future__ import annotations

from app.core.constants import (
    ContentStatus,
    DateStatus,
    MultimodalPredictionLabel,
    OverallVerdict,
    SourceStatus,
)


def derive_ai_overall_verdict(
    source_status: SourceStatus,
    content_status: ContentStatus | None,
    date_status: DateStatus | None,
) -> OverallVerdict:
    """For SOURCE_BASED / PHOTO_CARD claims, from the pipeline's own
    (source_status, content_status, date_status)."""
    if source_status == SourceStatus.NOT_FOUND:
        return OverallVerdict.FAKE
    if content_status == ContentStatus.ALTERED:
        return OverallVerdict.ALTERED
    if date_status == DateStatus.MISMATCHED:
        return OverallVerdict.MISLEADING
    return OverallVerdict.REAL


def derive_ai_overall_verdict_multimodal(
    prediction: MultimodalPredictionLabel | str,
) -> OverallVerdict:
    """For MULTIMODAL claims, from the BanglaBERT+EfficientNet binary call —
    the model can only say FAKE/NON_FAKE, so it never implies MISLEADING or
    ALTERED; only an expert vote can assign those."""
    return (
        OverallVerdict.FAKE
        if prediction == MultimodalPredictionLabel.FAKE
        else OverallVerdict.REAL
    )
