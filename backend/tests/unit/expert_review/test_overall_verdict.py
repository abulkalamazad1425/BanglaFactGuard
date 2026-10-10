from app.core.constants import MultimodalPredictionLabel, OverallVerdict
from app.features.expert_review.overall_verdict import derive_ai_overall_verdict_multimodal


def test_the_multimodal_model_only_ever_implies_fake_or_real():
    assert derive_ai_overall_verdict_multimodal(MultimodalPredictionLabel.FAKE) == OverallVerdict.FAKE
    assert derive_ai_overall_verdict_multimodal(MultimodalPredictionLabel.NON_FAKE) == OverallVerdict.REAL
