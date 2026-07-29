
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


_INFER_POOL = ThreadPoolExecutor(
    max_workers=_SETTINGS.multimodal.inference_thread_workers,
    thread_name_prefix="multimodal-infer",
)


_LABEL_MAP = {0: "NON_FAKE", 1: "FAKE"}

_IMG_MEAN = [0.485, 0.456, 0.406]
_IMG_STD = [0.229, 0.224, 0.225]


@dataclasses.dataclass(frozen=True)
class PredictionResult:

    prediction: str
    confidence_fake: float
    confidence_real: float
    raw_logits: tuple[float, float]


class MultimodalInferenceEngine:

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





    def _forward_pass_sync(
        self,
        body_text: str,
        image_bytes: bytes,
    ) -> PredictionResult:
        loader = self._loader
        device = loader.device
        cfg = self._cfg


        enc = loader.tokenizer(
            body_text,
            padding="max_length",
            truncation=True,
            max_length=cfg.max_seq_length,
            return_tensors="pt",
        )
        input_ids = enc["input_ids"].to(device)
        attn_mask = enc["attention_mask"].to(device)


        try:
            pil_img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        except Exception:
            logger.warning("inference_image_decode_failed_using_blank")
            pil_img = Image.new("RGB", (cfg.img_size, cfg.img_size), (0, 0, 0))

        img_tensor = self._eval_transform(pil_img).unsqueeze(0).to(device)


        with torch.no_grad():
            img_feats: torch.Tensor = loader.img_backbone(img_tensor)
            text_feats: torch.Tensor = loader.text_backbone(input_ids, attn_mask)
            logits: torch.Tensor = loader.classifier(img_feats, text_feats)
            probs: torch.Tensor = F.softmax(logits, dim=1).squeeze(0)

        probs_np = probs.cpu().numpy()
        pred_idx = int(np.argmax(probs_np))
        label = _LABEL_MAP[pred_idx]

        return PredictionResult(
            prediction=label,
            confidence_fake=float(probs_np[1]),
            confidence_real=float(probs_np[0]),
            raw_logits=(float(logits[0, 0].item()), float(logits[0, 1].item())),
        )
