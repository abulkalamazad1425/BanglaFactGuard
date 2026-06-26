"""
app/features/multimodal/pipeline/embedding_extractor.py
========================================================
Multimodal embedding extraction for intelligent duplicate detection.

## Strategy

Duplicate detection operates at three independent levels so that neither
text nor image alone can mask a genuine difference:

    Level 1 — Text (768-dim BanglaBERT [CLS])
        Captures semantic meaning of the body text.
        Threshold: cosine ≥ 0.92  (very high — near-identical wording)

    Level 2 — Image (1792-dim EfficientNet-B4 global-pool)
        Captures visual content of the uploaded image.
        Threshold: cosine ≥ 0.85  (high — same or near-identical image)

    Level 3 — Combined (2560-dim, L2-normalised concat of Level 1 + 2)
        Joint multimodal fingerprint used as the primary pre-filter.
        Threshold: cosine ≥ 0.90

A *cache hit* requires ALL THREE thresholds to pass.  This means:
  • Same text + swapped image → image embedding diverges → fresh prediction.
  • Same image + reworded text → text embedding diverges → fresh prediction.
  • Genuinely identical submission → all three pass → cached result returned.

## Threading

Both BanglaBERT and EfficientNet are CPU-bound PyTorch models. Encoding
is dispatched to a dedicated `ThreadPoolExecutor` to keep the asyncio
event loop unblocked.
"""

from __future__ import annotations

import asyncio
import io
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import torch
import structlog
from PIL import Image
from torchvision import transforms

from app.core.config import get_settings
from app.features.multimodal.pipeline.model_loader import MultimodalModelLoader

logger = structlog.get_logger(__name__)
_SETTINGS = get_settings()

# Thread pool for CPU-bound encoding
_ENCODE_POOL = ThreadPoolExecutor(
    max_workers=_SETTINGS.multimodal.inference_thread_workers,
    thread_name_prefix="multimodal-embed",
)

# Eval-time image transform — matches training eval_transform exactly
_IMG_MEAN = [0.485, 0.456, 0.406]
_IMG_STD = [0.229, 0.224, 0.225]


def _build_eval_transform(img_size: int) -> transforms.Compose:
    return transforms.Compose([
        transforms.Resize((img_size, img_size)),
        transforms.ToTensor(),
        transforms.Normalize(mean=_IMG_MEAN, std=_IMG_STD),
    ])


class MultimodalEmbeddingExtractor:
    """
    Extracts text, image, and combined embeddings from a submission.

    Must be initialised with a loaded ``MultimodalModelLoader`` (i.e. after
    the application lifespan startup has completed).

    Args:
        loader: A fully loaded ``MultimodalModelLoader`` instance.
    """

    def __init__(self, loader: MultimodalModelLoader) -> None:
        self._loader = loader
        self._cfg = _SETTINGS.multimodal
        self._eval_transform = _build_eval_transform(self._cfg.img_size)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def extract_text_embedding(self, body_text: str) -> np.ndarray:
        """
        Encode ``body_text`` through BanglaBERT and return the [CLS] embedding.

        Args:
            body_text: Article body text (the sole text input to the model).

        Returns:
            Numpy float32 array of shape (768,).
        """
        loop = asyncio.get_event_loop()
        embedding: np.ndarray = await loop.run_in_executor(
            _ENCODE_POOL,
            lambda: self._text_encode_sync(body_text),
        )
        return embedding

    async def extract_image_embedding(self, image_bytes: bytes) -> np.ndarray:
        """
        Encode an image through EfficientNet-B4 and return the feature vector.

        Args:
            image_bytes: Raw image file content (JPEG/PNG/etc.).

        Returns:
            Numpy float32 array of shape (1792,).
        """
        loop = asyncio.get_event_loop()
        embedding: np.ndarray = await loop.run_in_executor(
            _ENCODE_POOL,
            lambda: self._image_encode_sync(image_bytes),
        )
        return embedding

    async def extract_all_embeddings(
        self,
        body_text: str,
        image_bytes: bytes,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Extract text, image, and combined embeddings concurrently.

        The two backbone calls are independent and run concurrently via
        ``asyncio.gather``.

        Args:
            body_text:   Article body text.
            image_bytes: Raw image bytes.

        Returns:
            Tuple of (text_embedding [768,], image_embedding [1792,],
                      combined_embedding [2560,]).
        """
        text_emb, img_emb = await asyncio.gather(
            self.extract_text_embedding(body_text),
            self.extract_image_embedding(image_bytes),
        )
        combined_emb = self._build_combined_embedding(text_emb, img_emb)
        return text_emb, img_emb, combined_emb

    # ------------------------------------------------------------------
    # Similarity helpers (used by the service for dedup decisions)
    # ------------------------------------------------------------------

    @staticmethod
    def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        """
        Compute cosine similarity between two float32 vectors.

        Both vectors are L2-normalised before the dot product, so the result
        is in [-1, 1]. We clamp to [0, 1] for use as a similarity score.

        Args:
            a: First embedding vector.
            b: Second embedding vector.

        Returns:
            Cosine similarity clamped to [0.0, 1.0].
        """
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        raw = float(np.dot(a, b) / (norm_a * norm_b))
        return float(np.clip(raw, 0.0, 1.0))

    def is_duplicate(
        self,
        *,
        query_text_emb: np.ndarray,
        query_img_emb: np.ndarray,
        query_combined_emb: np.ndarray,
        candidate_text_emb: np.ndarray,
        candidate_img_emb: np.ndarray,
        candidate_combined_emb: np.ndarray,
    ) -> tuple[bool, dict[str, float]]:
        """
        Decide whether a candidate prediction is a genuine duplicate of the
        current query by verifying all three modality thresholds.

        Returns:
            (is_dup, scores) where ``scores`` is a dict of the three
            cosine similarity values for logging/debugging.
        """
        cfg = self._cfg

        combined_sim = self.cosine_similarity(query_combined_emb, candidate_combined_emb)
        text_sim = self.cosine_similarity(query_text_emb, candidate_text_emb)
        image_sim = self.cosine_similarity(query_img_emb, candidate_img_emb)

        scores = {
            "combined_similarity": combined_sim,
            "text_similarity": text_sim,
            "image_similarity": image_sim,
        }

        is_dup = (
            combined_sim >= cfg.combined_sim_threshold
            and text_sim >= cfg.text_sim_threshold
            and image_sim >= cfg.image_sim_threshold
        )
        return is_dup, scores

    # ------------------------------------------------------------------
    # Synchronous encoding (run inside thread pool)
    # ------------------------------------------------------------------

    def _text_encode_sync(self, body_text: str) -> np.ndarray:
        """Tokenize and encode text through BanglaBERT — blocking call."""
        cfg = self._cfg
        tokenizer = self._loader.tokenizer
        text_backbone = self._loader.text_backbone
        device = self._loader.device

        enc = tokenizer(
            body_text,
            padding="max_length",
            truncation=True,
            max_length=cfg.max_seq_length,
            return_tensors="pt",
        )
        input_ids = enc["input_ids"].to(device)
        attn_mask = enc["attention_mask"].to(device)

        with torch.no_grad():
            feat: torch.Tensor = text_backbone(input_ids, attn_mask)  # [1, 768]

        return feat.squeeze(0).cpu().numpy().astype(np.float32)

    def _image_encode_sync(self, image_bytes: bytes) -> np.ndarray:
        """Decode image and encode through EfficientNet-B4 — blocking call."""
        img_backbone = self._loader.img_backbone
        device = self._loader.device

        try:
            pil_img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        except Exception:
            # Fallback to a blank image rather than crashing the whole request
            logger.warning("multimodal_image_decode_failed_using_blank")
            pil_img = Image.new("RGB", (self._cfg.img_size, self._cfg.img_size), (0, 0, 0))

        tensor = self._eval_transform(pil_img).unsqueeze(0).to(device)  # [1, 3, H, W]

        with torch.no_grad():
            feat: torch.Tensor = img_backbone(tensor)  # [1, 1792]

        return feat.squeeze(0).cpu().numpy().astype(np.float32)

    # ------------------------------------------------------------------
    # Combined embedding
    # ------------------------------------------------------------------

    @staticmethod
    def _build_combined_embedding(
        text_emb: np.ndarray,
        img_emb: np.ndarray,
    ) -> np.ndarray:
        """
        Concatenate text and image embeddings and L2-normalise.

        L2 normalisation ensures the combined vector lives on the unit
        hypersphere, making cosine similarity equivalent to the dot product
        and the magnitude of each modality's contribution equal.

        Returns:
            Float32 array of shape (2560,).
        """
        combined = np.concatenate([text_emb, img_emb], axis=0).astype(np.float32)
        norm = np.linalg.norm(combined)
        if norm > 0:
            combined = combined / norm
        return combined
