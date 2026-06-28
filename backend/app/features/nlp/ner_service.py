"""
app/services/ner_service.py
============================
Named Entity Recognition (NER) service using BanglaBERT for Stage 8.

## Model

BanglaBERT NER (csebuetnlp/banglabert) fine-tuned on Bangla NER corpus.
Entity types: PER (person), LOC (location), ORG (organisation), MISC (other).

## Architecture

Loaded once at startup alongside LaBSE. Uses a HuggingFace `pipeline`
with aggregation strategy "simple" to merge sub-word tokens into full spans.

## Async wrapping

HuggingFace pipeline inference is synchronous/CPU-bound.
All NER calls are dispatched to a shared `ThreadPoolExecutor`.

## Output normalisation

Entity spans are lowercased and stripped for set-intersection comparison.
Only entities of type PER, LOC, ORG are used in entity_match scoring —
MISC entities are filtered out as too noisy.
"""

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
    """
    Singleton NER service backed by BanglaBERT.

    Usage::

        service = NERService()
        await service.load()
        entities = await service.extract_entities("প্রধানমন্ত্রী শেখ হাসিনা ঢাকায়")
        # → ["শেখ হাসিনা", "ঢাকা"]
    """

    _pipeline = None
    _loaded: bool = False

    async def load(self) -> None:
        """Load BanglaBERT NER pipeline (called once at startup)."""
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
                    device=-1,  # CPU; change to 0 for GPU
                ),
            )
            NERService._loaded = True
            logger.info("banglabert_ner_loaded")
        except Exception as exc:
            logger.error("banglabert_ner_load_failed", error=str(exc))
            raise

    async def extract_entities(self, text: str) -> list[str]:
        """
        Extract named entities from text.

        Args:
            text: Input Bangla or mixed text.

        Returns:
            List of entity span strings (lowercased, deduplicated).
            Returns empty list if NER is not loaded or extraction fails.
        """
        if not NERService._loaded or NERService._pipeline is None:
            logger.warning("ner_not_loaded_returning_empty")
            return []

        if not text or len(text.strip()) < 5:
            return []

        # Truncate to avoid exceeding BanglaBERT's 512 token limit
        truncated = text[:1000]

        loop = asyncio.get_event_loop()
        try:
            raw_entities = await loop.run_in_executor(
                _NER_POOL,
                lambda: NERService._pipeline(truncated),  # type: ignore[misc]
            )
        except Exception as exc:  # noqa: BLE001
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
        """
        Compute entity set-intersection ratio between claim and article.

        Score = |claim_entities ∩ article_entities| / max(|claim_entities|, 1)

        Args:
            claim_entities:   Entities extracted from claim headline + body.
            article_entities: Entities extracted from article title + body.

        Returns:
            Float in [0.0, 1.0]. 1.0 if no claim entities (nothing to match).
        """
        if not claim_entities:
            return 1.0

        claim_set = {e.lower().strip() for e in claim_entities if e.strip()}
        article_set = {e.lower().strip() for e in article_entities if e.strip()}

        if not claim_set:
            return 1.0

        matched = len(claim_set & article_set)
        return matched / len(claim_set)

    async def extract_entities_with_types(self, text: str) -> list[tuple[str, str]]:
        """
        Extract named entities with their type labels from text.

        Unlike `extract_entities` which returns only span strings, this returns
        (entity_span, entity_type) tuples. Entity types are normalised to the
        base category: PER, LOC, or ORG.

        Used by S10 for entity-type-aware substitution detection — checking
        whether claim PER entities were replaced with different PER entities
        (deliberate substitution) vs. completely different entity types
        (topic mismatch).

        Args:
            text: Input Bangla or mixed text.

        Returns:
            List of (entity_span, entity_type) tuples, deduplicated.
            Returns empty list if NER is not loaded or extraction fails.
        """
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
        except Exception:  # noqa: BLE001
            return []

        # Normalise entity group labels to base types (PER, LOC, ORG)
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
        """
        Detect whether entities were substituted with same-type replacements.

        This is a stronger signal of deliberate manipulation than raw entity
        overlap: if the claim mentions person A but the article mentions
        person B (both PER), the entity was likely deliberately replaced.

        Returns True if:
        - The claim has entities of a given type (e.g. PER)
        - The article also has entities of the same type
        - But the specific entities differ (substitution, not absence)

        Args:
            claim_typed:   (entity_span, type) pairs from the claim.
            article_typed: (entity_span, type) pairs from the article.

        Returns:
            True if same-type entity substitution is detected.
        """
        if not claim_typed or not article_typed:
            return False

        # Group entities by type
        claim_by_type: dict[str, set[str]] = {}
        for span, etype in claim_typed:
            claim_by_type.setdefault(etype, set()).add(span)

        article_by_type: dict[str, set[str]] = {}
        for span, etype in article_typed:
            article_by_type.setdefault(etype, set()).add(span)

        # Check each type: if both sides have entities of this type but
        # the overlap is zero, it's a same-type substitution.
        for etype, claim_ents in claim_by_type.items():
            article_ents = article_by_type.get(etype, set())
            if article_ents and not (claim_ents & article_ents):
                # Both sides have this entity type but zero overlap → substitution
                return True

        return False
