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


_ENCODE_POOL = ThreadPoolExecutor(
    max_workers=_SETTINGS.multimodal.inference_thread_workers,
    thread_name_prefix="multimodal-embed",
)


_IMG_MEAN = [0.485, 0.456, 0.406]
_IMG_STD = [0.229, 0.224, 0.225]


def _build_eval_transform(img_size: int) -> transforms.Compose:
    return transforms.Compose(
        [
            transforms.Resize((img_size, img_size)),
            transforms.ToTensor(),
            transforms.Normalize(mean=_IMG_MEAN, std=_IMG_STD),
        ]
    )


class MultimodalEmbeddingExtractor:

    def __init__(self, loader: MultimodalModelLoader) -> None:
        self._loader = loader
        self._cfg = _SETTINGS.multimodal
        self._eval_transform = _build_eval_transform(self._cfg.img_size)

    async def extract_text_embedding(self, body_text: str) -> np.ndarray:
        loop = asyncio.get_event_loop()
        embedding: np.ndarray = await loop.run_in_executor(
            _ENCODE_POOL,
            lambda: self._text_encode_sync(body_text),
        )
        return embedding

    async def extract_image_embedding(self, image_bytes: bytes) -> np.ndarray:
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
        text_emb, img_emb = await asyncio.gather(
            self.extract_text_embedding(body_text),
            self.extract_image_embedding(image_bytes),
        )
        combined_emb = self._build_combined_embedding(text_emb, img_emb)
        return text_emb, img_emb, combined_emb

    @staticmethod
    def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
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
        cfg = self._cfg

        combined_sim = self.cosine_similarity(
            query_combined_emb, candidate_combined_emb
        )
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

    def _text_encode_sync(self, body_text: str) -> np.ndarray:
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
            feat: torch.Tensor = text_backbone(input_ids, attn_mask)

        return feat.squeeze(0).cpu().numpy().astype(np.float32)

    def _image_encode_sync(self, image_bytes: bytes) -> np.ndarray:
        img_backbone = self._loader.img_backbone
        device = self._loader.device

        try:
            pil_img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        except Exception:

            logger.warning("multimodal_image_decode_failed_using_blank")
            pil_img = Image.new(
                "RGB", (self._cfg.img_size, self._cfg.img_size), (0, 0, 0)
            )

        tensor = self._eval_transform(pil_img).unsqueeze(0).to(device)

        with torch.no_grad():
            feat: torch.Tensor = img_backbone(tensor)

        return feat.squeeze(0).cpu().numpy().astype(np.float32)

    @staticmethod
    def _build_combined_embedding(
        text_emb: np.ndarray,
        img_emb: np.ndarray,
    ) -> np.ndarray:
        combined = np.concatenate([text_emb, img_emb], axis=0).astype(np.float32)
        norm = np.linalg.norm(combined)
        if norm > 0:
            combined = combined / norm
        return combined
