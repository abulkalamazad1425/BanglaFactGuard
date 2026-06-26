"""
app/features/multimodal/pipeline/model_loader.py
=================================================
Loads the trained BanglaBERT + EfficientNet-B4 checkpoint from disk once
at application startup and makes the components available to the inference
engine and embedding extractor.

Checkpoint layout expected in ``MULTIMODAL_MODEL_DIR``:
    img_backbone.pt    — EfficientNetBackbone state dict
    text_backbone.pt   — BanglaBERTBackbone state dict
    classifier.pt      — MultiFusionFake state dict
    tokenizer/         — Saved HuggingFace tokenizer directory

All three PyTorch modules are set to ``eval()`` mode after loading.
Weights are loaded with ``weights_only=True`` (safe loading, PyTorch ≥ 2.0).

Thread safety:
    ``load()`` uses a class-level ``_loaded`` flag and an asyncio.Lock to
    ensure only one coroutine executes the blocking weight-load even if
    multiple requests arrive simultaneously before loading completes.
"""

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

# Dedicated thread pool for heavy blocking model I/O
_LOAD_POOL = ThreadPoolExecutor(
    max_workers=1,
    thread_name_prefix="multimodal-loader",
)


class MultimodalModelLoader:
    """
    Singleton-style loader that holds references to all three trained model
    components and the tokenizer after startup.

    Usage (inside FastAPI lifespan)::

        loader = MultimodalModelLoader()
        await loader.load()
        app.state.multimodal_loader = loader

    Consumer code can then access::

        loader.img_backbone
        loader.text_backbone
        loader.classifier
        loader.tokenizer
        loader.device
    """

    # Class-level flag ensures weights are loaded exactly once per process
    # even if multiple MultimodalModelLoader instances are created (shouldn't
    # happen in practice since main.py creates one and stores it on app.state).
    _loaded: bool = False
    _lock: asyncio.Lock | None = None

    def __init__(self) -> None:
        cfg = _SETTINGS.multimodal
        self._cfg = cfg
        self._device = torch.device(cfg.device)

        # These are populated by load()
        self._img_backbone: EfficientNetBackbone | None = None
        self._text_backbone: BanglaBERTBackbone | None = None
        self._classifier: MultiFusionFake | None = None
        self._tokenizer: AutoTokenizer | None = None

    # ------------------------------------------------------------------
    # Async load
    # ------------------------------------------------------------------

    async def load(self) -> None:
        """
        Load all model weights and tokenizer from disk.

        Must be called once from the FastAPI lifespan startup hook before
        any prediction requests are processed. Subsequent calls are no-ops.

        Raises:
            InferenceError: If any weight file or the tokenizer directory
                            is missing, or if ``torch.load`` fails.
        """
        # Lazy-create the lock on the event loop that is actually running
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
        """Raise InferenceError early if required files are missing."""
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
        """Blocking weight-load — runs in a thread pool executor."""
        cfg = self._cfg
        device = self._device

        # ── Reconstruct architecture (pretrained=False — weights come from .pt) ──
        img_backbone = EfficientNetBackbone(cfg.image_model_name, pretrained=False).to(device)
        text_backbone = BanglaBERTBackbone(cfg.text_model_name).to(device)
        classifier = MultiFusionFake(
            img_dim=img_backbone.out_dim,
            text_dim=text_backbone.out_dim,
            num_classes=cfg.num_classes,
            dropout=cfg.dropout,
        ).to(device)

        # ── Load state dicts ────────────────────────────────────────────
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

        # ── Tokenizer ───────────────────────────────────────────────────
        tokenizer = AutoTokenizer.from_pretrained(os.path.join(model_dir, "tokenizer"))

        # ── Eval mode ───────────────────────────────────────────────────
        img_backbone.eval()
        text_backbone.eval()
        classifier.eval()

        return img_backbone, text_backbone, classifier, tokenizer

    # ------------------------------------------------------------------
    # Properties (raise ModelNotLoadedError if accessed before load())
    # ------------------------------------------------------------------

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
