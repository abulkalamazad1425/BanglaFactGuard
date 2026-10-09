"""The AI-implied Overall verdict for MULTIMODAL claims (FAKE/REAL only)."""

from __future__ import annotations

from app.core.constants import MultimodalPredictionLabel, OverallVerdict


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
