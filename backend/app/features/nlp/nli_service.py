

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
    _pipeline = None
    _loaded: bool = False
    _labels_ok: bool = False
    _audit: dict = {}

    @property
    def audit(self) -> dict:
        return dict(NLIService._audit)

    async def load(self) -> None:
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
