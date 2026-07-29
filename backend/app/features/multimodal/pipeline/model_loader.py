
from __future__ import annotations

import asyncio
import os
from concurrent.futures import ThreadPoolExecutor

import torch
import structlog
from transformers import AutoTokenizer

from app.core.config import get_settings
from app.core.exceptions import ModelNotLoadedError, InferenceError
from app.features.multimodal.pipeline.model_architecture import (
    EfficientNetBackbone,
    BanglaBERTBackbone,
    MultiFusionFake,
)

logger = structlog.get_logger(__name__)
_SETTINGS = get_settings()


_LOAD_POOL = ThreadPoolExecutor(
    max_workers=1,
    thread_name_prefix="multimodal-loader",
)


class MultimodalModelLoader:




    _loaded: bool = False
    _lock: asyncio.Lock | None = None

    def __init__(self) -> None:
        cfg = _SETTINGS.multimodal
        self._cfg = cfg
        self._device = torch.device(cfg.device)


        self._img_backbone: EfficientNetBackbone | None = None
        self._text_backbone: BanglaBERTBackbone | None = None
        self._classifier: MultiFusionFake | None = None
        self._tokenizer: AutoTokenizer | None = None





    async def load(self) -> None:

        if MultimodalModelLoader._lock is None:
            MultimodalModelLoader._lock = asyncio.Lock()

        async with MultimodalModelLoader._lock:
            if MultimodalModelLoader._loaded:
                return

            model_dir = self._cfg.model_dir
            logger.info("multimodal_model_loading", model_dir=model_dir, device=str(self._device))

            self._validate_model_dir(model_dir)

            loop = asyncio.get_event_loop()
            try:
                result = await loop.run_in_executor(
                    _LOAD_POOL,
                    lambda: self._load_sync(model_dir),
                )
            except Exception as exc:
                logger.error("multimodal_model_load_failed", error=str(exc))
                raise InferenceError(
                    model_name="MultiBanFake_BanglaBERT_EfficientNetB4",
                    cause=f"Weight loading failed: {exc}",
                ) from exc

            self._img_backbone, self._text_backbone, self._classifier, self._tokenizer = result
            MultimodalModelLoader._loaded = True
            logger.info(
                "multimodal_model_loaded",
                device=str(self._device),
                img_out_dim=self._img_backbone.out_dim,
                text_out_dim=self._text_backbone.out_dim,
            )

    def _validate_model_dir(self, model_dir: str) -> None:
        required = ["img_backbone.pt", "text_backbone.pt", "classifier.pt"]
        missing = [f for f in required if not os.path.isfile(os.path.join(model_dir, f))]
        if not os.path.isdir(os.path.join(model_dir, "tokenizer")):
            missing.append("tokenizer/")
        if missing:
            raise InferenceError(
                model_name="MultiBanFake_BanglaBERT_EfficientNetB4",
                cause=(
                    f"Missing files in MULTIMODAL_MODEL_DIR ({model_dir}): "
                    + ", ".join(missing)
                    + ". Download from the training Drive folder and place them here."
                ),
            )

    def _load_sync(
        self, model_dir: str
    ) -> tuple[EfficientNetBackbone, BanglaBERTBackbone, MultiFusionFake, AutoTokenizer]:
        cfg = self._cfg
        device = self._device


        img_backbone = EfficientNetBackbone(cfg.image_model_name, pretrained=False).to(device)
        text_backbone = BanglaBERTBackbone(cfg.text_model_name).to(device)
        classifier = MultiFusionFake(
            img_dim=img_backbone.out_dim,
            text_dim=text_backbone.out_dim,
            num_classes=cfg.num_classes,
            dropout=cfg.dropout,
        ).to(device)


        img_backbone.load_state_dict(
            torch.load(
                os.path.join(model_dir, "img_backbone.pt"),
                map_location=device,
                weights_only=True,
            )
        )
        text_backbone.load_state_dict(
            torch.load(
                os.path.join(model_dir, "text_backbone.pt"),
                map_location=device,
                weights_only=True,
            )
        )
        classifier.load_state_dict(
            torch.load(
                os.path.join(model_dir, "classifier.pt"),
                map_location=device,
                weights_only=True,
            )
        )


        tokenizer = AutoTokenizer.from_pretrained(os.path.join(model_dir, "tokenizer"))


        img_backbone.eval()
        text_backbone.eval()
        classifier.eval()

        return img_backbone, text_backbone, classifier, tokenizer





    @property
    def is_loaded(self) -> bool:
        return MultimodalModelLoader._loaded

    @property
    def img_backbone(self) -> EfficientNetBackbone:
        if self._img_backbone is None:
            raise ModelNotLoadedError("EfficientNetBackbone")
        return self._img_backbone

    @property
    def text_backbone(self) -> BanglaBERTBackbone:
        if self._text_backbone is None:
            raise ModelNotLoadedError("BanglaBERTBackbone")
        return self._text_backbone

    @property
    def classifier(self) -> MultiFusionFake:
        if self._classifier is None:
            raise ModelNotLoadedError("MultiFusionFake")
        return self._classifier

    @property
    def tokenizer(self) -> AutoTokenizer:
        if self._tokenizer is None:
            raise ModelNotLoadedError("BanglaBERTTokenizer")
        return self._tokenizer

    @property
    def device(self) -> torch.device:
        return self._device
