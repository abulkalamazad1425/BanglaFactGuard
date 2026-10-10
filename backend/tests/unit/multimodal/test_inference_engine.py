"""Classifier output -> label and confidences; reusing the extractor's
features gives exactly the full forward pass."""

import pytest

from app.core.exceptions import InferenceError
from app.features.multimodal.pipeline.embedding_extractor import MultimodalEmbeddingExtractor
from app.features.multimodal.pipeline.inference_engine import MultimodalInferenceEngine
from tests.helpers.multimodal import TinyLoader, png


@pytest.mark.parametrize("logits,label", [((0.0, 2.0), "FAKE"), ((3.0, 1.0), "NON_FAKE")])
async def test_label_and_confidences_follow_the_softmax(logits, label):
    result = await MultimodalInferenceEngine(TinyLoader(logits)).predict("বিবরণ", png())
    assert result.prediction == label and result.raw_logits == logits
    assert result.confidence_fake + result.confidence_real == pytest.approx(1.0)
    assert (result.confidence_fake > 0.5) is (label == "FAKE")


async def test_reusing_extracted_features_matches_the_full_forward_pass():
    loader = TinyLoader()
    body, image = "ঢাকায় নতুন মেট্রোরেল চালু হয়েছে।", png((10, 200, 30))
    await MultimodalInferenceEngine(loader).predict(body, image)
    text, img, _ = await MultimodalEmbeddingExtractor(loader).extract_all_embeddings(body, image)
    await MultimodalInferenceEngine(loader).predict_from_features(text, img)
    (full_img, full_text), (reused_img, reused_text) = loader.classifier_inputs
    assert full_img.allclose(reused_img) and full_text.allclose(reused_text)
    await MultimodalInferenceEngine(loader).predict(body, b"not-an-image")  # decode fallback, not an error


async def test_a_model_failure_is_an_inference_error():
    loader = TinyLoader()

    def broken(*args):
        raise RuntimeError("shape mismatch")

    loader.classifier = broken
    with pytest.raises(InferenceError):
        await MultimodalInferenceEngine(loader).predict_from_features([1.0], [1.0])
