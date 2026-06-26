"""
app/features/multimodal/pipeline/inference_engine.py
====================================================
Runs the full multimodal forward pass and returns a structured prediction.

The engine:
  1. Preprocesses the body_text through the BanglaBERT tokenizer.
  2. Preprocesses the raw image bytes through the eval-time image transform.
  3. Runs the EfficientNet-B4 and BanglaBERT backbones (concurrently on CPU
     by offloading to a thread pool).
  4. Feeds the concatenated features through the MultiFusionFake classifier.
  5. Applies softmax and returns the label + per-class probabilities.

All inference is wrapped in ``torch.no_grad()`` and the models are expected
to already be in ``.eval()`` mode (set by MultimodalModelLoader.load()).
"""

from __future__ import annotations

import asyncio
import dataclasses
import io
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import torch
import torch.nn.functional as F
import structlog
from PIL import Image
from torchvision import transforms

from app.core.config import get_settings
from app.core.exceptions import InferenceError
from app.features.multimodal.pipeline.model_loader import MultimodalModelLoader

logger = structlog.get_logger(__name__)
_SETTINGS = get_settings()

# Thread pool for the full forward pass (CPU-bound)
_INFER_POOL = ThreadPoolExecutor(
    max_workers=_SETTINGS.multimodal.inference_thread_workers,
    thread_name_prefix="multimodal-infer",
)

# Label mapping — matches training: 0 = Real, 1 = Fake
_LABEL_MAP = {0: "NON_FAKE", 1: "FAKE"}

_IMG_MEAN = [0.485, 0.456, 0.406]
_IMG_STD = [0.229, 0.224, 0.225]


@dataclasses.dataclass(frozen=True)
class PredictionResult:
    """
    Result of a single multimodal inference call.

    Attributes:
        prediction:      ``"FAKE"`` or ``"NON_FAKE"``.
        confidence_fake: Softmax probability for the FAKE class (0.0–1.0).
        confidence_real: Softmax probability for the NON_FAKE class (0.0–1.0).
        raw_logits:      Raw 2-element logit array before softmax (for debugging).
    """

    prediction: str
    confidence_fake: float
    confidence_real: float
    raw_logits: tuple[float, float]


class MultimodalInferenceEngine:
    """
    Executes the trained BanglaBERT + EfficientNet-B4 forward pass.

    Args:
        loader: A fully loaded ``MultimodalModelLoader`` instance.
    """

    def __init__(self, loader: MultimodalModelLoader) -> None:
        self._loader = loader
        self._cfg = _SETTINGS.multimodal
        self._eval_transform = transforms.Compose([
            transforms.Resize((self._cfg.img_size, self._cfg.img_size)),
            transforms.ToTensor(),
            transforms.Normalize(mean=_IMG_MEAN, std=_IMG_STD),
        ])

    async def predict(
        self,
        body_text: str,
        image_bytes: bytes,
    ) -> PredictionResult:
        """
        Run the full multimodal inference pipeline for one news item.

        Note: Only ``body_text`` is used as the text input — the headline
        is stored for display but not passed to the model (per design decision).

        Args:
            body_text:   Article body text (tokenized by BanglaBERT).
            image_bytes: Raw image bytes (decoded by PIL).

        Returns:
            A ``PredictionResult`` with label and confidence scores.

        Raises:
            InferenceError: If the forward pass raises an unexpected exception.
        """
        loop = asyncio.get_event_loop()
        try:
            result: PredictionResult = await loop.run_in_executor(
                _INFER_POOL,
                lambda: self._forward_pass_sync(body_text, image_bytes),
            )
        except InferenceError:
            raise
        except Exception as exc:
            logger.error("multimodal_inference_failed", error=str(exc), exc_info=True)
            raise InferenceError(
                model_name="MultiBanFake_BanglaBERT_EfficientNetB4",
                cause=str(exc),
            ) from exc

        logger.info(
            "multimodal_inference_complete",
            prediction=result.prediction,
            confidence_fake=round(result.confidence_fake, 4),
            confidence_real=round(result.confidence_real, 4),
        )
        return result

    # ------------------------------------------------------------------
    # Synchronous forward pass (runs inside thread pool)
    # ------------------------------------------------------------------

    def _forward_pass_sync(
        self,
        body_text: str,
        image_bytes: bytes,
    ) -> PredictionResult:
        """
        Full PyTorch forward pass — blocking; must run in a thread pool.

        Steps:
          1. Tokenize body_text via BanglaBERT tokenizer.
          2. Decode + transform image bytes.
          3. img_backbone(image) → [1, 1792]
          4. text_backbone(input_ids, attn_mask) → [1, 768]
          5. classifier(img_feats, text_feats) → [1, 2] logits
          6. softmax → probabilities
        """
        loader = self._loader
        device = loader.device
        cfg = self._cfg

        # ── Text preprocessing ─────────────────────────────────────────
        enc = loader.tokenizer(
            body_text,
            padding="max_length",
            truncation=True,
            max_length=cfg.max_seq_length,
            return_tensors="pt",
        )
        input_ids = enc["input_ids"].to(device)      # [1, max_seq_length]
        attn_mask = enc["attention_mask"].to(device)  # [1, max_seq_length]

        # ── Image preprocessing ────────────────────────────────────────
        try:
            pil_img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        except Exception:
            logger.warning("inference_image_decode_failed_using_blank")
            pil_img = Image.new("RGB", (cfg.img_size, cfg.img_size), (0, 0, 0))

        img_tensor = self._eval_transform(pil_img).unsqueeze(0).to(device)  # [1, 3, H, W]

        # ── Forward pass ───────────────────────────────────────────────
        with torch.no_grad():
            img_feats: torch.Tensor = loader.img_backbone(img_tensor)        # [1, 1792]
            text_feats: torch.Tensor = loader.text_backbone(input_ids, attn_mask)  # [1, 768]
            logits: torch.Tensor = loader.classifier(img_feats, text_feats)  # [1, 2]
            probs: torch.Tensor = F.softmax(logits, dim=1).squeeze(0)        # [2]

        probs_np = probs.cpu().numpy()
        pred_idx = int(np.argmax(probs_np))
        label = _LABEL_MAP[pred_idx]

        return PredictionResult(
            prediction=label,
            confidence_fake=float(probs_np[1]),
            confidence_real=float(probs_np[0]),
            raw_logits=(float(logits[0, 0].item()), float(logits[0, 1].item())),
        )
