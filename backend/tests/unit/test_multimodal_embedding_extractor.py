"""
tests/unit/test_multimodal_embedding_extractor.py
==================================================
Unit tests for MultimodalEmbeddingExtractor.

These tests mock the PyTorch backbones so they run without GPU/model weights.
"""

from __future__ import annotations

import numpy as np
import pytest
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_loader(text_dim: int = 768, img_dim: int = 1792):
    """Build a mock MultimodalModelLoader that returns fake embeddings."""
    loader = MagicMock()
    loader.device = "cpu"
    loader.is_loaded = True

    # text_backbone: returns zeros tensor
    import torch
    text_feat = torch.zeros(1, text_dim)
    loader.text_backbone.return_value = text_feat

    # img_backbone: returns ones tensor
    img_feat = torch.ones(1, img_dim)
    loader.img_backbone.return_value = img_feat

    # tokenizer
    loader.tokenizer.return_value = {
        "input_ids": torch.zeros(1, 128, dtype=torch.long),
        "attention_mask": torch.ones(1, 128, dtype=torch.long),
    }
    return loader


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestCombinedEmbedding:
    """Test _build_combined_embedding static method."""

    def test_output_shape(self):
        from app.features.multimodal.pipeline.embedding_extractor import (
            MultimodalEmbeddingExtractor,
        )
        text_emb = np.random.rand(768).astype(np.float32)
        img_emb = np.random.rand(1792).astype(np.float32)
        combined = MultimodalEmbeddingExtractor._build_combined_embedding(text_emb, img_emb)
        assert combined.shape == (2560,)

    def test_output_is_unit_norm(self):
        from app.features.multimodal.pipeline.embedding_extractor import (
            MultimodalEmbeddingExtractor,
        )
        text_emb = np.random.rand(768).astype(np.float32)
        img_emb = np.random.rand(1792).astype(np.float32)
        combined = MultimodalEmbeddingExtractor._build_combined_embedding(text_emb, img_emb)
        norm = float(np.linalg.norm(combined))
        assert abs(norm - 1.0) < 1e-5, f"Expected unit norm, got {norm}"

    def test_zero_input_does_not_raise(self):
        from app.features.multimodal.pipeline.embedding_extractor import (
            MultimodalEmbeddingExtractor,
        )
        text_emb = np.zeros(768, dtype=np.float32)
        img_emb = np.zeros(1792, dtype=np.float32)
        # Should not raise — zero norm is handled gracefully
        combined = MultimodalEmbeddingExtractor._build_combined_embedding(text_emb, img_emb)
        assert combined.shape == (2560,)


class TestCosineSimilarity:
    """Test cosine_similarity static method."""

    def test_identical_vectors(self):
        from app.features.multimodal.pipeline.embedding_extractor import (
            MultimodalEmbeddingExtractor,
        )
        v = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        sim = MultimodalEmbeddingExtractor.cosine_similarity(v, v)
        assert abs(sim - 1.0) < 1e-6

    def test_orthogonal_vectors(self):
        from app.features.multimodal.pipeline.embedding_extractor import (
            MultimodalEmbeddingExtractor,
        )
        a = np.array([1.0, 0.0], dtype=np.float32)
        b = np.array([0.0, 1.0], dtype=np.float32)
        sim = MultimodalEmbeddingExtractor.cosine_similarity(a, b)
        assert abs(sim - 0.0) < 1e-6

    def test_result_clamped_to_zero(self):
        """Negative cosine similarity is clamped to 0.0."""
        from app.features.multimodal.pipeline.embedding_extractor import (
            MultimodalEmbeddingExtractor,
        )
        a = np.array([1.0, 0.0], dtype=np.float32)
        b = np.array([-1.0, 0.0], dtype=np.float32)
        sim = MultimodalEmbeddingExtractor.cosine_similarity(a, b)
        assert sim == 0.0, "Negative cosine should be clamped to 0"

    def test_zero_vector_returns_zero(self):
        from app.features.multimodal.pipeline.embedding_extractor import (
            MultimodalEmbeddingExtractor,
        )
        a = np.zeros(10, dtype=np.float32)
        b = np.ones(10, dtype=np.float32)
        sim = MultimodalEmbeddingExtractor.cosine_similarity(a, b)
        assert sim == 0.0


class TestIsDuplicate:
    """Test is_duplicate logic — all three thresholds must pass."""

    def _make_extractor(self):
        from app.features.multimodal.pipeline.embedding_extractor import (
            MultimodalEmbeddingExtractor,
        )
        loader = MagicMock()
        loader.is_loaded = True
        with patch("app.core.config.get_settings") as mock_settings:
            mock_settings.return_value.multimodal.text_sim_threshold = 0.92
            mock_settings.return_value.multimodal.image_sim_threshold = 0.85
            mock_settings.return_value.multimodal.combined_sim_threshold = 0.90
            mock_settings.return_value.multimodal.img_size = 380
            mock_settings.return_value.multimodal.inference_thread_workers = 1
            return MultimodalEmbeddingExtractor(loader)

    def test_identical_inputs_are_duplicate(self):
        extractor = self._make_extractor()
        v_text = np.ones(768, dtype=np.float32)
        v_img = np.ones(1792, dtype=np.float32)
        v_combined = np.ones(2560, dtype=np.float32)
        is_dup, scores = extractor.is_duplicate(
            query_text_emb=v_text,
            query_img_emb=v_img,
            query_combined_emb=v_combined,
            candidate_text_emb=v_text,
            candidate_img_emb=v_img,
            candidate_combined_emb=v_combined,
        )
        assert is_dup is True
        assert scores["text_similarity"] == pytest.approx(1.0, abs=1e-5)

    def test_different_image_breaks_cache_hit(self):
        """Same text + orthogonal image → not a duplicate."""
        extractor = self._make_extractor()
        text_emb = np.ones(768, dtype=np.float32)

        # Same text embedding for both
        img_q = np.zeros(1792, dtype=np.float32)
        img_q[0] = 1.0  # orthogonal to candidate

        img_c = np.zeros(1792, dtype=np.float32)
        img_c[1] = 1.0

        combined_q = MultimodalEmbeddingExtractor._build_combined_embedding(text_emb, img_q)
        combined_c = MultimodalEmbeddingExtractor._build_combined_embedding(text_emb, img_c)

        from app.features.multimodal.pipeline.embedding_extractor import (
            MultimodalEmbeddingExtractor,
        )
        is_dup, scores = extractor.is_duplicate(
            query_text_emb=text_emb,
            query_img_emb=img_q,
            query_combined_emb=combined_q,
            candidate_text_emb=text_emb,
            candidate_img_emb=img_c,
            candidate_combined_emb=combined_c,
        )
        assert is_dup is False, "Orthogonal images should not be a duplicate"
        assert scores["image_similarity"] == pytest.approx(0.0, abs=1e-5)
