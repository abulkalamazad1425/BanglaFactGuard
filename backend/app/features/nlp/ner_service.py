"""
app/features/nlp/ner_service.py
=================================
Bangla named-entity recognition (PER/LOC/ORG) for Stages 8 and 10.

## Model and what is (not) known about it

`settings.ml.ner_model_name`, default `neuropark/sahajBERT-NER`, an ALBERT
model pretrained on Bangla and fine-tuned for token classification. A *base*
pretrained checkpoint is not evidence of a functioning NER model — the
previous default (`csebuetnlp/banglabert`, an ELECTRA pretraining checkpoint)
loaded without error, got a randomly initialised head and silently produced
no PER/LOC/ORG at all. This service therefore AUDITS the model at load time
and exposes the result; it never reports "no entities" when the model is
simply not working:

1. **Label audit** — the checkpoint's `id2label` must contain PER, LOC and ORG
   (BIO prefixes stripped). Generic `LABEL_n` names mean the head cannot be
   mapped to entity types and the service marks itself UNAVAILABLE.
2. **Smoke test** — a fixed Bangla sentence with a known person, place and
   organisation must yield at least one entity of a kept type. A model that
   cannot tag it is treated as non-functional.

The audit proves the checkpoint is wired and loosely functional, not that it
is accurate: no Bangla NER accuracy benchmark has been run for this project.

## Normalisation and truncation

Surfaces are normalised with the same `normalize_for_match` used for every
other comparison (NFC, zero-width removal, SentencePiece `▁` removed, digits
-> ASCII, casefold). Long text is split into sentence chunks (<= 350 chars,
well under the 512-token limit) and each chunk is tagged — the earlier
`text[:1000]` truncation silently dropped every entity after the first ~1000
characters.

## Results

`extract_mentions()` returns an `NERResult`. `available=False` means "could
not run" (not loaded / failed audit / inference error); callers must report
the entity metric as unavailable, never as zero entities or a pass.
"""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

import structlog
from transformers import pipeline as hf_pipeline

from app.core.config import get_settings
from app.features.verification.analysis.entities import EntityMention
from app.features.verification.analysis.text import chunk_text, normalize_for_match

logger = structlog.get_logger(__name__)
_SETTINGS = get_settings()

_NER_MODEL = _SETTINGS.ml.ner_model_name
_KEPT_TYPES = {"PER", "LOC", "ORG"}
_SMOKE_SENTENCE = "প্রধানমন্ত্রী শেখ হাসিনা ঢাকায় জাতিসংঘের সদর দপ্তরে বৈঠক করেছেন।"
_MAX_CHUNK_CHARS = 350
_MAX_CHUNKS = 40

_NER_POOL = ThreadPoolExecutor(
    max_workers=_SETTINGS.ml.ner_thread_workers,
    thread_name_prefix="bangla-ner",
)


def _base_type(label: str) -> str | None:
    """B-PER / I-PER / PER -> PER; anything else (O, LABEL_3) -> None."""
    base = label.split("-", 1)[-1].upper()
    return base if base in _KEPT_TYPES else None


@dataclass
class NERResult:
    available: bool
    mentions: list[EntityMention] = field(default_factory=list)
    error: str | None = None
    truncated: bool = False


class NERService:

    _pipeline = None
    _loaded: bool = False
    # Audit state. `usable` is the only flag callers need.
    _labels_ok: bool = False
    _smoke_ok: bool = False
    _audit: dict = {}

    @property
    def usable(self) -> bool:
        return bool(
            NERService._loaded
            and NERService._pipeline is not None
            and NERService._labels_ok
            and NERService._smoke_ok
        )

    @property
    def audit(self) -> dict:
        return dict(NERService._audit)

    async def load(self) -> None:
        if NERService._loaded:
            return
        loop = asyncio.get_event_loop()
        logger.info("loading_ner_model", model=_NER_MODEL)
        try:
            NERService._pipeline = await loop.run_in_executor(
                _NER_POOL,
                lambda: hf_pipeline(
                    "ner",
                    model=_NER_MODEL,
                    aggregation_strategy="simple",
                    device=-1,
                ),
            )
            NERService._loaded = True
        except Exception as exc:
            logger.error("ner_model_load_failed", error=str(exc))
            raise
        await self._run_audit()

    async def _run_audit(self) -> None:
        pipe = NERService._pipeline
        id2label: dict = {}
        try:
            id2label = dict(pipe.model.config.id2label)  # type: ignore[union-attr]
        except Exception as exc:  # noqa: BLE001
            logger.error("ner_audit_no_labels", error=str(exc))
        types = {_base_type(str(v)) for v in id2label.values()} - {None}
        labels_ok = _KEPT_TYPES.issubset(types)
        NERService._labels_ok = labels_ok

        smoke_entities: list[str] = []
        if labels_ok:
            res = await self._tag_chunks([_SMOKE_SENTENCE])
            smoke_entities = [f"{m.text}:{m.type}" for m in res.mentions] if res.available else []
        NERService._smoke_ok = bool(smoke_entities)
        NERService._audit = {
            "model": _NER_MODEL,
            "labels": sorted({str(v) for v in id2label.values()}),
            "labels_map_to_per_loc_org": labels_ok,
            "smoke_entities": smoke_entities,
            "usable": NERService._labels_ok and NERService._smoke_ok,
            "accuracy_validated": False,
        }
        if self.usable:
            logger.info("ner_model_loaded", **NERService._audit)
        else:
            logger.error(
                "ner_model_not_functional",
                hint=(
                    "The checkpoint did not pass the label/smoke audit; entity "
                    "metrics will be reported UNAVAILABLE rather than empty."
                ),
                **NERService._audit,
            )

    async def _tag_chunks(self, chunks: list[str]) -> NERResult:
        pipe = NERService._pipeline
        if pipe is None:
            return NERResult(False, error="NER model not loaded")
        loop = asyncio.get_event_loop()
        mentions: list[EntityMention] = []
        seen: set[tuple[str, str]] = set()
        try:
            for chunk in chunks:
                raw = await loop.run_in_executor(_NER_POOL, lambda c=chunk: pipe(c))
                for ent in raw or []:
                    etype = _base_type(str(ent.get("entity_group", ent.get("entity", ""))))
                    word = normalize_for_match(str(ent.get("word", "")))
                    if not etype or len(word) < 2 or word.startswith("##"):
                        continue
                    if (word, etype) not in seen:
                        seen.add((word, etype))
                        mentions.append(EntityMention(word, etype))
        except Exception as exc:  # noqa: BLE001
            logger.warning("ner_extraction_failed", error=str(exc))
            return NERResult(False, error=str(exc))
        return NERResult(True, mentions)

    async def extract_mentions(self, text: str) -> NERResult:
        """Typed entity mentions across the WHOLE text (chunked, not truncated)."""
        if not self.usable:
            return NERResult(False, error="NER unavailable (not loaded or failed audit)")
        if not text or len(text.strip()) < 5:
            return NERResult(True, [])
        chunks, truncated = chunk_text(text, max_chars=_MAX_CHUNK_CHARS, max_chunks=_MAX_CHUNKS)
        result = await self._tag_chunks(chunks)
        result.truncated = truncated
        return result

    # ── legacy helpers (kept for callers outside S08/S10) ────────────────

    async def extract_entities(self, text: str) -> list[str]:
        res = await self.extract_mentions(text)
        return [m.text for m in res.mentions]

    async def extract_entities_with_types(self, text: str) -> list[tuple[str, str]]:
        res = await self.extract_mentions(text)
        return [(m.text, m.type) for m in res.mentions]
