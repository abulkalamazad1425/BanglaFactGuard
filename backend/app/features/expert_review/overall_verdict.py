"""AI-implied Overall verdict for MULTIMODAL claims only.

Business rule: the automated system never decides an Overall verdict
(Fake/Real/Misleading/Altered) for SOURCE_BASED or PHOTO_CARD claims — those
only ever get the three structured checks (source/content/date status), and
Overall is exclusively an expert-review outcome for them, with no AI-implied
default. See ``app/features/verification/pipeline/stages/s12_result_assembly.py``,
which has never produced an Overall verdict, and
``ExpertReviewService._finalize_or_escalate``'s structured branch, which
passes no tie-break preference for the Overall vote tally.

MULTIMODAL is the one submission type whose model (BanglaBERT+EfficientNet)
natively outputs a binary FAKE/NON_FAKE call as part of its own classification
— a pre-existing, separate design this function continues to serve as a
weighting/display helper for; it is not a general "automated overall verdict"
mechanism and is deliberately not used by the two source-verification flows.
"""

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
