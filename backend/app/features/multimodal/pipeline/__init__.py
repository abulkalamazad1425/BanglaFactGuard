"""
app/features/multimodal/pipeline/__init__.py
=============================================
Pipeline subpackage for the multimodal fake-news detection feature.

Exports:
    MultimodalModelLoader       — loads BanglaBERT + EfficientNet-B4 weights at startup
    MultimodalEmbeddingExtractor — extracts text/image/combined embeddings
    MultimodalInferenceEngine   — runs the full forward pass
"""

from app.features.multimodal.pipeline.model_loader import MultimodalModelLoader
from app.features.multimodal.pipeline.embedding_extractor import MultimodalEmbeddingExtractor
from app.features.multimodal.pipeline.inference_engine import MultimodalInferenceEngine

__all__ = [
    "MultimodalModelLoader",
    "MultimodalEmbeddingExtractor",
    "MultimodalInferenceEngine",
]
