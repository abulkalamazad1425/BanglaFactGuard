"""
app/services/nli_service.py
=============================
Natural Language Inference (NLI) service for contradiction detection (Stage 9).

## Model

`cross-encoder/nli-deberta-v3-small` — a DeBERTa-v3 cross-encoder fine-tuned
on MNLI, SNLI, and FEVER. Outputs entailment/contradiction/neutral probabilities.

## Why a cross-encoder (not bi-encoder)?

Cross-encoders process the premise and hypothesis jointly (concatenated input),
capturing fine-grained token interactions. This is critical for detecting subtle
numerical or entity-level contradictions that bi-encoders (like LaBSE) miss.

## Input truncation

DeBERTa input limit: 512 tokens. Combined premise+hypothesis is truncated to
~1500 characters (≈350 tokens per text, safely within limits).

## Async wrapping

HuggingFace `pipeline` is synchronous; runs in a dedicated `ThreadPoolExecutor`.

## Output

Returns `NLIScoresSchema` with entailment/contradiction/neutral probabilities.
The `contradiction_score` field in `VerificationScoresSchema` is set to the
NLI contradiction probability.
"""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor

import structlog
from transformers import pipeline as hf_pipeline

from app.core.config import get_settings
from app.features.verification.schemas import NLIScoresSchema
from app.shared.utils.text_cleaner import truncate_for_nli

logger = structlog.get_logger(__name__)
_SETTINGS = get_settings()

_NLI_MODEL = "cross-encoder/nli-deberta-v3-small"
_LABEL_MAP = {
    "ENTAILMENT": "entailment",
    "CONTRADICTION": "contradiction",
    "NEUTRAL": "neutral",
}

_NLI_POOL = ThreadPoolExecutor(
    max_workers=_SETTINGS.ml.nli_thread_workers,
    thread_name_prefix="deberta-nli",
)


class NLIService:
    """
    Singleton NLI service backed by DeBERTa-v3 cross-encoder.

    Usage::

        service = NLIService()
        await service.load()
        result = await service.predict(premise, hypothesis)
        # → NLIScoresSchema(entailment=0.87, contradiction=0.05, neutral=0.08)
    """

    _pipeline = None
    _loaded: bool = False

    async def load(self) -> None:
        """Load the DeBERTa NLI pipeline (called once at startup)."""
        if NLIService._loaded:
            return
        loop = asyncio.get_event_loop()
        logger.info("loading_nli_model", model=_NLI_MODEL)
        try:
            NLIService._pipeline = await loop.run_in_executor(
                _NLI_POOL,
                lambda: hf_pipeline(
                    "text-classification",
                    model=_NLI_MODEL,
                    top_k=None,
                    device=-1,
                ),
            )
            NLIService._loaded = True
            logger.info("nli_model_loaded")
        except Exception as exc:
            logger.error("nli_model_load_failed", error=str(exc))
            raise

    async def predict(self, premise: str, hypothesis: str) -> NLIScoresSchema | None:
        """
        Run NLI inference for a (premise, hypothesis) pair.

        Args:
            premise:    The retrieved article text (or truncated version).
            hypothesis: The claim headline (what we are testing).

        Returns:
            NLIScoresSchema with entailment/contradiction/neutral probabilities,
            or None if the model is not loaded or inference fails.
        """
        if not NLIService._loaded or NLIService._pipeline is None:
            logger.warning("nli_not_loaded_returning_none")
            return None


        truncated_premise = truncate_for_nli(premise, max_chars=1200)
        truncated_hyp = truncate_for_nli(hypothesis, max_chars=300)

        loop = asyncio.get_event_loop()
        try:
            raw_output = await loop.run_in_executor(
                _NLI_POOL,
                lambda: NLIService._pipeline(
                    {"text": truncated_premise, "text_pair": truncated_hyp}
                ),
            )
        except Exception as exc:
            logger.warning("nli_inference_failed", error=str(exc))
            return None

        return self._parse_output(raw_output)

    @staticmethod
    def _parse_output(raw_output: list[dict]) -> NLIScoresSchema | None:
        """
        Parse DeBERTa pipeline output into NLIScoresSchema.

        The pipeline returns a list of dicts: [{"label": "ENTAILMENT", "score": 0.87}, ...]

        Args:
            raw_output: Raw HuggingFace pipeline output.

        Returns:
            NLIScoresSchema or None if parsing fails.
        """
        if not raw_output:
            return None
        try:
            scores: dict[str, float] = {}
            for item in raw_output:
                label = _LABEL_MAP.get(item["label"].upper(), item["label"].lower())
                scores[label] = float(item["score"])

            return NLIScoresSchema(
                entailment=scores.get("entailment", 0.0),
                contradiction=scores.get("contradiction", 0.0),
                neutral=scores.get("neutral", 0.0),
            )
        except (KeyError, ValueError, TypeError) as exc:
            logger.warning("nli_output_parse_failed", error=str(exc))
            return None


