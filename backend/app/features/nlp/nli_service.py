"""
app/features/nlp/nli_service.py
================================
Natural Language Inference (NLI) service used by the Headline Alteration
semantic assessment (S09: source title vs claim headline).

## Model

`settings.ml.nli_model_name`, default `MoritzLaurer/mDeBERTa-v3-base-mnli-xnli`
— an mDeBERTa-v3-base cross-encoder fine-tuned on XNLI (15 languages) + MNLI,
built on a 100-language multilingual vocabulary. Outputs entailment/
contradiction/neutral probabilities.

Previously hardcoded to `cross-encoder/nli-deberta-v3-small`, a DeBERTa-v3
cross-encoder fine-tuned on MNLI/SNLI/FEVER — all English-only datasets, on
an English-only vocabulary. Directly verified: that tokenizer splits a
71-character Bangla sentence into 71 tokens, almost entirely single Unicode
code points, because its SentencePiece vocabulary has essentially no Bangla
subword units. A model cannot represent semantics it cannot tokenize, so its
contradiction/entailment scores on Bangla input were not meaningful signal —
whatever confidence the pipeline displayed was not a reliable detection of
anything happening in the Bangla text itself. The replacement model's
tokenizer was verified on the same sentence to produce 27 well-formed
subword tokens with zero `[UNK]`s (e.g. "প্রধানমন্ত্রী" as one token). This is
a tokenization-coverage check, not a measured accuracy benchmark — Bengali is
not among the 15 XNLI languages this checkpoint was fine-tuned/evaluated on;
it is covered only via the base model's multilingual pretraining and
cross-lingual transfer from the fine-tuned languages, which is the standard,
well-documented mechanism this family of models relies on for languages
outside its evaluation set, but is not independently validated here. A
genuine Bangla NLI accuracy evaluation (labeled Bangla NLI pairs) should
still happen separately before this score is trusted for high-stakes
decisions.

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
Used only by the Headline Alteration comparison (source title vs claim
headline, in both directions) - never on article bodies.
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

_NLI_MODEL = _SETTINGS.ml.nli_model_name
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
    # Label audit: the pipeline output is mapped by label NAME, so the
    # checkpoint must expose exactly entailment/neutral/contradiction. A model
    # with generic LABEL_n names would be silently mis-mapped (label order is
    # model-specific), so it is refused rather than guessed at.
    _labels_ok: bool = False
    _audit: dict = {}

    @property
    def audit(self) -> dict:
        return dict(NLIService._audit)

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
            self._audit_labels()
        except Exception as exc:
            logger.error("nli_model_load_failed", error=str(exc))
            raise

    def _audit_labels(self) -> None:
        try:
            id2label = dict(NLIService._pipeline.model.config.id2label)  # type: ignore[union-attr]
        except Exception as exc:  # noqa: BLE001
            logger.error("nli_audit_no_labels", error=str(exc))
            id2label = {}
        names = {str(v).lower() for v in id2label.values()}
        NLIService._labels_ok = names == {"entailment", "neutral", "contradiction"}
        NLIService._audit = {
            "model": _NLI_MODEL,
            "label_order": [str(id2label[k]) for k in sorted(id2label)],
            "labels_ok": NLIService._labels_ok,
            "bangla_validated": False,
        }
        if NLIService._labels_ok:
            logger.info("nli_model_loaded", **NLIService._audit)
        else:
            logger.error(
                "nli_labels_unrecognised",
                hint="Label names are not entailment/neutral/contradiction; NLI output is ignored.",
                **NLIService._audit,
            )

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
        if not NLIService._loaded or NLIService._pipeline is None or not NLIService._labels_ok:
            logger.warning("nli_not_usable_returning_none")
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
