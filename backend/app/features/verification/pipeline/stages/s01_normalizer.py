"""
app/pipelines/stages/s01_normalizer.py
========================================
Stage 1: Input Normalization

## Responsibility

Transforms raw API inputs into normalised, canonical forms that all
downstream stages depend on:

1. **Text normalisation**: Apply Unicode NFC, zero-width removal, Bangla
   punctuation mapping, and whitespace collapse to headline and body.

2. **Source normalisation**: Resolve the raw claimed_source string to a
   canonical domain (e.g. "prothomalo.com") using:
   a. Static alias map (KNOWN_SOURCE_ALIASES)
   b. URL extraction (if the source looks like a URL)
   c. DB lookup via SourceRepository (dynamic registry)
   d. If unresolved: stores None and sets stage error (non-fatal —
      pipeline continues but with reduced search accuracy)

3. **Claim hash computation**: Generate the SHA-256 deduplication key
   from (normalised_headline, normalised_source) — used by Stage 2.

## Criticality: CRITICAL
If normalisation fails entirely (e.g. completely empty headline after
stripping), a StageError is raised and the orchestrator aborts.
Source resolution failure is NON-FATAL.
"""

from __future__ import annotations

import structlog

from app.core.constants import PipelineStageID
from app.core.exceptions import NormalizationError
from app.features.verification.pipeline.context import PipelineContext
from app.features.sources.repository import SourceRepository
from app.shared.utils.bangla_normalizer import (
    extract_canonical_domain,
    normalize_bangla_text,
    normalize_source_name,
)
from app.shared.utils.hashing import compute_claim_hash

logger = structlog.get_logger(__name__)


class InputNormalizerStage:
    """
    Stage 1: Normalize headline, body, and claimed source; compute claim hash.

    Dependencies (injected via constructor):
        source_repo: Used for DB-level source resolution when static map fails.
    """

    stage_id = PipelineStageID.S01_NORMALIZER

    def __init__(self, source_repo: SourceRepository) -> None:
        """
        Args:
            source_repo: SourceRepository for dynamic source resolution.
        """
        self.source_repo = source_repo

    async def execute(self, context: PipelineContext) -> PipelineContext:
        """
        Normalise all text inputs and compute the claim hash.

        Args:
            context: Pipeline context with raw_headline, raw_news_body,
                     raw_claimed_source, and published_date set.

        Returns:
            Context with normalized_headline, normalized_body,
            normalized_source, and claim_hash populated.

        Raises:
            NormalizationError: If the headline is empty after normalisation.
        """
        log = logger.bind(
            stage=self.stage_id.value,
            claim_id=str(context.claim_id) if context.claim_id else "pending",
        )

        # ------------------------------------------------------------------
        # 1. Normalise headline (CRITICAL — must succeed)
        # ------------------------------------------------------------------
        normalised_headline = normalize_bangla_text(
            context.raw_headline, normalize_digits=False
        )
        if not normalised_headline:
            raise NormalizationError(
                stage_id=self.stage_id.value,
                message="Headline is empty after normalisation.",
                details={"raw_headline": context.raw_headline},
            )
        context.normalized_headline = normalised_headline
        log.debug(
            "headline_normalised",
            original_len=len(context.raw_headline),
            normalised_len=len(normalised_headline),
        )

        # ------------------------------------------------------------------
        # 2. Normalise body (NON-CRITICAL — may be None)
        # ------------------------------------------------------------------
        if context.raw_news_body:
            context.normalized_body = normalize_bangla_text(
                context.raw_news_body, normalize_digits=False
            )
        else:
            context.normalized_body = None

        # ------------------------------------------------------------------
        # 3. Normalise source (NON-CRITICAL — resolution failure is tolerated)
        # ------------------------------------------------------------------
        context.normalized_source = await self._resolve_source(
            context.raw_claimed_source, context, log
        )
        
        if context.normalized_source:
            source_record = await self.source_repo.get_by_canonical_name(context.normalized_source)
            if source_record:
                context.source_config = {
                    "name": source_record.display_name,
                    "body_selectors": source_record.body_selectors or [],
                    "title_selectors": source_record.title_selectors or [],
                    "date_selectors": source_record.date_selectors or [],
                    "internal_search_url": source_record.internal_search_url,
                    "article_url_patterns": source_record.article_url_patterns or [],
                }

        # ------------------------------------------------------------------
        # 4. Compute claim hash
        # ------------------------------------------------------------------
        # Use normalised_source if resolved, else fall back to raw source
        # to still produce a stable hash even when resolution fails
        source_for_hash = context.normalized_source or context.raw_claimed_source
        context.claim_hash = compute_claim_hash(
            context.normalized_headline, source_for_hash
        )
        log.info(
            "claim_hash_computed",
            claim_hash=context.claim_hash[:16] + "...",  # log only prefix for brevity
            normalized_source=context.normalized_source,
        )

        return context

    async def _resolve_source(
        self,
        raw_source: str,
        context: PipelineContext,
        log: structlog.BoundLogger,
    ) -> str | None:
        """
        Resolve the raw claimed source to a canonical domain name.

        Resolution order:
          1. Try URL extraction (if raw_source looks like a URL).
          2. Try static alias map (normalize_source_name).
          3. Try DB lookup via SourceRepository.

        Args:
            raw_source: The raw claimed source string from the request.
            context:    Pipeline context (for recording non-fatal errors).
            log:        Bound logger with stage/claim context.

        Returns:
            Canonical domain string or None if unresolvable.
        """
        if not raw_source:
            context.record_stage_error(
                self.stage_id, "claimed_source is empty"
            )
            return None

        # Step 1: URL extraction
        canonical = extract_canonical_domain(raw_source)
        if canonical:
            log.debug("source_resolved_via_url_extraction", canonical=canonical)
            return canonical

        # Step 2: Static alias map
        canonical = normalize_source_name(raw_source)
        if canonical:
            log.debug("source_resolved_via_static_map", canonical=canonical)
            return canonical

        # Step 3: DB lookup
        try:
            source_record = await self.source_repo.resolve_source(raw_source)
            if source_record:
                canonical = source_record.canonical_name
                log.debug("source_resolved_via_db", canonical=canonical)
                return canonical
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "source_db_lookup_failed",
                raw_source=raw_source,
                error=str(exc),
            )

        # Unresolved — record non-fatal error, continue
        log.warning("source_unresolved", raw_source=raw_source)
        context.record_stage_error(
            self.stage_id,
            f"Source could not be resolved: {raw_source!r}",
        )
        return None

