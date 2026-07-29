
from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor

import structlog
from transformers import pipeline as hf_pipeline

from app.core.config import get_settings

logger = structlog.get_logger(__name__)
_SETTINGS = get_settings()

_NER_MODEL = "csebuetnlp/banglabert"
_ENTITY_TYPES_KEPT = {"PER", "LOC", "ORG", "B-PER", "B-LOC", "B-ORG",
                       "I-PER", "I-LOC", "I-ORG"}

_NER_POOL = ThreadPoolExecutor(
    max_workers=_SETTINGS.ml.ner_thread_workers,
    thread_name_prefix="banglabert-ner",
)


class NERService:

    _pipeline = None
    _loaded: bool = False

    async def load(self) -> None:
        if NERService._loaded:
            return
        loop = asyncio.get_event_loop()
        logger.info("loading_banglabert_ner", model=_NER_MODEL)
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
            logger.info("banglabert_ner_loaded")
        except Exception as exc:
            logger.error("banglabert_ner_load_failed", error=str(exc))
            raise

    async def extract_entities(self, text: str) -> list[str]:
        if not NERService._loaded or NERService._pipeline is None:
            logger.warning("ner_not_loaded_returning_empty")
            return []

        if not text or len(text.strip()) < 5:
            return []


        truncated = text[:1000]

        loop = asyncio.get_event_loop()
        try:
            raw_entities = await loop.run_in_executor(
                _NER_POOL,
                lambda: NERService._pipeline(truncated),
            )
        except Exception as exc:
            logger.warning("ner_extraction_failed", error=str(exc))
            return []

        seen: set[str] = set()
        entities: list[str] = []
        for ent in (raw_entities or []):
            entity_group = ent.get("entity_group", ent.get("entity", ""))
            word = ent.get("word", "").strip().lower()
            if entity_group in _ENTITY_TYPES_KEPT and word and word not in seen:
                seen.add(word)
                entities.append(word)

        return entities

    def compute_entity_overlap(
        self,
        claim_entities: list[str],
        article_entities: list[str],
    ) -> float:
        if not claim_entities:
            return 1.0

        claim_set = {e.lower().strip() for e in claim_entities if e.strip()}
        article_set = {e.lower().strip() for e in article_entities if e.strip()}

        if not claim_set:
            return 1.0

        matched = len(claim_set & article_set)
        return matched / len(claim_set)

    async def extract_entities_with_types(self, text: str) -> list[tuple[str, str]]:
        if not NERService._loaded or NERService._pipeline is None:
            return []

        if not text or len(text.strip()) < 5:
            return []

        truncated = text[:1000]
        loop = asyncio.get_event_loop()
        try:
            raw_entities = await loop.run_in_executor(
                _NER_POOL,
                lambda: NERService._pipeline(truncated),
            )
        except Exception:
            return []


        _TYPE_MAP = {
            "PER": "PER", "B-PER": "PER", "I-PER": "PER",
            "LOC": "LOC", "B-LOC": "LOC", "I-LOC": "LOC",
            "ORG": "ORG", "B-ORG": "ORG", "I-ORG": "ORG",
        }

        seen: set[str] = set()
        typed_entities: list[tuple[str, str]] = []
        for ent in (raw_entities or []):
            entity_group = ent.get("entity_group", ent.get("entity", ""))
            word = ent.get("word", "").strip().lower()
            base_type = _TYPE_MAP.get(entity_group)
            if base_type and word and word not in seen:
                seen.add(word)
                typed_entities.append((word, base_type))

        return typed_entities

    @staticmethod
    def compute_typed_entity_substitution(
        claim_typed: list[tuple[str, str]],
        article_typed: list[tuple[str, str]],
    ) -> bool:
        if not claim_typed or not article_typed:
            return False


        claim_by_type: dict[str, set[str]] = {}
        for span, etype in claim_typed:
            claim_by_type.setdefault(etype, set()).add(span)

        article_by_type: dict[str, set[str]] = {}
        for span, etype in article_typed:
            article_by_type.setdefault(etype, set()).add(span)



        for etype, claim_ents in claim_by_type.items():
            article_ents = article_by_type.get(etype, set())
            if article_ents and not (claim_ents & article_ents):

                return True

        return False
