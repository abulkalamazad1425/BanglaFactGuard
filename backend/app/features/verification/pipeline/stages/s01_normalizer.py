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

    stage_id = PipelineStageID.S01_NORMALIZER

    def __init__(self, source_repo: SourceRepository) -> None:
        self.source_repo = source_repo

    async def execute(self, context: PipelineContext) -> PipelineContext:
        log = logger.bind(
            stage=self.stage_id.value,
            submission_id=str(context.submission_id) if context.submission_id else "pending",
        )

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

        if context.raw_news_body:
            context.normalized_body = normalize_bangla_text(
                context.raw_news_body, normalize_digits=False
            )
        else:
            context.normalized_body = None

        context.normalized_source = await self._resolve_source(
            context.raw_claimed_source, context, log
        )

        if context.normalized_source:
            source_record = await self.source_repo.get_by_canonical_name(
                context.normalized_source
            )
            if source_record:
                context.source_config = {
                    "name": source_record.display_name,
                    "body_selectors": source_record.body_selectors or [],
                    "title_selectors": source_record.title_selectors or [],
                    "date_selectors": source_record.date_selectors or [],
                    "internal_search_url": source_record.internal_search_url,
                    "article_url_patterns": source_record.article_url_patterns or [],
                }

        source_for_hash = context.normalized_source or context.raw_claimed_source
        context.content_hash = compute_claim_hash(
            context.normalized_headline, source_for_hash
        )
        log.info(
            "content_hash_computed",
            content_hash=context.content_hash[:16] + "...",
            normalized_source=context.normalized_source,
        )

        return context

    async def _resolve_source(
        self,
        raw_source: str,
        context: PipelineContext,
        log: structlog.BoundLogger,
    ) -> str | None:
        if not raw_source:
            context.record_stage_error(self.stage_id, "claimed_source is empty")
            return None

        canonical = extract_canonical_domain(raw_source)
        if canonical:
            log.debug("source_resolved_via_url_extraction", canonical=canonical)
            return canonical

        canonical = normalize_source_name(raw_source)
        if canonical:
            log.debug("source_resolved_via_static_map", canonical=canonical)
            return canonical

        try:
            source_record = await self.source_repo.resolve_source(raw_source)
            if source_record:
                canonical = source_record.canonical_name
                log.debug("source_resolved_via_db", canonical=canonical)
                return canonical
        except Exception as exc:
            log.warning(
                "source_db_lookup_failed",
                raw_source=raw_source,
                error=str(exc),
            )

        log.warning("source_unresolved", raw_source=raw_source)
        context.record_stage_error(
            self.stage_id,
            f"Source could not be resolved: {raw_source!r}",
        )
        return None
