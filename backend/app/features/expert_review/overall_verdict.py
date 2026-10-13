from __future__ import annotations

from app.core.constants import MultimodalPredictionLabel, OverallVerdict


def derive_ai_overall_verdict_multimodal(
    prediction: MultimodalPredictionLabel | str,
) -> OverallVerdict:
    return (
        OverallVerdict.FAKE
        if prediction == MultimodalPredictionLabel.FAKE
        else OverallVerdict.REAL
    )
