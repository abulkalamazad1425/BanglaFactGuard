from app.core.constants import MultimodalPredictionLabel
from app.shared.status_labels import ai_decision_label


def test_ai_decision_is_only_ever_likely_fake_or_likely_real():
    assert ai_decision_label(MultimodalPredictionLabel.FAKE) == "Likely Fake"
    assert ai_decision_label("fake") == "Likely Fake"
    assert ai_decision_label(MultimodalPredictionLabel.NON_FAKE) == "Likely Real"
    assert ai_decision_label("ANY_OTHER_CLASS") == "Likely Real"
    assert ai_decision_label(None) is None
