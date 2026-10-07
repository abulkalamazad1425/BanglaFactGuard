"""With the real weights: classifying the extractor's features gives exactly
the same result as the full forward pass. Opt-in (needs the multimodal
weights in MULTIMODAL_MODEL_DIR and the cached BanglaBERT config):
set BFG_REAL_MODEL_TESTS=1."""

import io
import os

import numpy as np
import pytest
from PIL import Image

pytestmark = pytest.mark.skipif(
    os.environ.get("BFG_REAL_MODEL_TESTS") != "1",
    reason="set BFG_REAL_MODEL_TESTS=1 to run with the real multimodal weights",
)


def _png(seed: int, size=(640, 420)) -> bytes:
    rng = np.random.default_rng(seed)
    arr = (rng.random((size[1], size[0], 3)) * 255).astype("uint8")
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, format="PNG")
    return buf.getvalue()


CASES = [
    ("ঢাকায় নতুন মেট্রোরেল চালু হয়েছে। আজ সকালে উদ্বোধন করা হয়।", _png(1)),
    ("সব স্কুল বন্ধ রাখার সিদ্ধান্তের একটি ভুয়া খবর ছড়িয়েছে।", _png(2)),
    ("ক্রিকেট দল আজ জয় পেয়েছে " * 30, _png(3, (300, 900))),
    ("Short English body.", b"not-an-image"),  # decode fallback path
]


@pytest.mark.asyncio
async def test_feature_reuse_matches_full_forward_pass():
    from app.features.multimodal.pipeline.embedding_extractor import MultimodalEmbeddingExtractor
    from app.features.multimodal.pipeline.inference_engine import MultimodalInferenceEngine
    from app.features.multimodal.pipeline.model_loader import MultimodalModelLoader

    loader = MultimodalModelLoader()
    await loader.load()
    extractor, engine = MultimodalEmbeddingExtractor(loader), MultimodalInferenceEngine(loader)

    for body, image in CASES:
        full = await engine.predict(body_text=body, image_bytes=image)
        text_emb, img_emb, _ = await extractor.extract_all_embeddings(body_text=body, image_bytes=image)
        reused = await engine.predict_from_features(text_emb, img_emb)
        assert reused.prediction == full.prediction
        assert reused.confidence_fake == pytest.approx(full.confidence_fake, abs=1e-6)
        assert reused.confidence_real == pytest.approx(full.confidence_real, abs=1e-6)
        assert reused.raw_logits == pytest.approx(full.raw_logits, abs=1e-5)
