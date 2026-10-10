"""Backbone features for duplicate detection: a submission is a duplicate only
when text, image AND combined similarity all clear their thresholds."""

import numpy as np
import pytest

from app.features.multimodal.pipeline.embedding_extractor import MultimodalEmbeddingExtractor as X
from tests.helpers.multimodal import TinyLoader, png


def test_cosine_similarity_is_clamped_to_0_1():
    a, b = np.array([1.0, 0.0]), np.array([0.0, 1.0])
    assert X.cosine_similarity(a, a) == pytest.approx(1.0)
    assert X.cosine_similarity(a, b) == 0.0
    assert X.cosine_similarity(a, -a) == 0.0
    assert X.cosine_similarity(np.zeros(2), a) == 0.0


def test_combined_embedding_is_the_unit_normalised_concatenation():
    combined = X._build_combined_embedding(np.random.rand(768).astype(np.float32), np.random.rand(1792).astype(np.float32))
    assert combined.shape == (2560,) and abs(float(np.linalg.norm(combined)) - 1.0) < 1e-5
    assert X._build_combined_embedding(np.zeros(2), np.zeros(3)).shape == (5,)


def test_a_different_image_is_never_a_duplicate():
    extractor = X(TinyLoader())
    text = np.ones(768, dtype=np.float32)
    img_a, img_b = np.eye(1792, dtype=np.float32)[0], np.eye(1792, dtype=np.float32)[1]

    def check(query_img, cand_img):
        return extractor.is_duplicate(
            query_text_emb=text, query_img_emb=query_img, query_combined_emb=X._build_combined_embedding(text, query_img),
            candidate_text_emb=text, candidate_img_emb=cand_img, candidate_combined_emb=X._build_combined_embedding(text, cand_img),
        )

    same, scores = check(img_a, img_a)
    assert same and scores["text_similarity"] == pytest.approx(1.0)
    different, scores = check(img_a, img_b)
    assert not different and scores["image_similarity"] == 0.0


async def test_features_come_from_both_backbones_and_an_unreadable_image_does_not_fail():
    extractor = X(TinyLoader())
    text, red, combined = await extractor.extract_all_embeddings("শিরোনাম ও বিবরণ", png((255, 0, 0)))
    assert text.shape == (8,) and red.shape == (3,) and combined.shape == (11,) and red[0] > red[1]
    _, blank, _ = await extractor.extract_all_embeddings("x", b"not-an-image")  # a blank image stands in
    assert blank.shape == (3,) and not np.allclose(blank, red)
