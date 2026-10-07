from __future__ import annotations

import structlog

from app.core.constants import PipelineStageID
from app.core.exceptions import NormalizationError
from app.features.verification.pipeline.context import PipelineContext
from app.features.sources.repository import SourceRepository
from app.features.sources.resolution import resolve_claimed_source
from app.shared.utils.bangla_normalizer import extract_canonical_domain, normalize_bangla_text
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
            context.raw_claimed_source, log
        )
        if context.normalized_source is None:
            # Fail closed, not silently unrestricted: s04_source_search.py's
            # domain filter only applies when a domain is known, so letting
            # an unresolved source through here would search the whole web
            # rather than just the claimed outlet. The service layer already
            # pre-checks this before the pipeline even starts (see
            # VerificationService.register_claim/verify and
            # PhotoCardService.process_submission) — reaching here unresolved means that
            # guard was bypassed, so this is a backstop, not the primary path.
            raise NormalizationError(
                stage_id=self.stage_id.value,
                message=f"Claimed source could not be resolved: {context.raw_claimed_source!r}",
                details={"claimed_source": context.raw_claimed_source},
            )

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
                # Registered channels for this outlet: S04 filters candidate
                # hosts and S05 validates FINAL redirected hosts against them.
                "allowed_domains": [
                    d
                    for d in (
                        extract_canonical_domain(source_record.base_url or ""),
                        *(extract_canonical_domain(str(a)) for a in (source_record.aliases or [])),
                    )
                    if d
                ],
            }

        # The single identity function (shared with registration, S02, S12 and
        # the photo-card flow): headline, body (only if the scope has one),
        # canonical source, claimed date, scope and pipeline version.
        context.content_hash = compute_claim_hash(
            context.normalized_headline,
            context.normalized_source,
            context.claim_scope,
            body=context.normalized_body,
            published_date=context.published_date,
        )
        log.info(
            "content_hash_computed",
            content_hash=context.content_hash[:16] + "...",
            normalized_source=context.normalized_source,
            claim_scope=context.claim_scope.value,
        )

        return context

    async def _resolve_source(
        self,
        raw_source: str,
        log: structlog.BoundLogger,
    ) -> str | None:
        canonical = await resolve_claimed_source(raw_source, self.source_repo)
        if canonical:
            log.debug("source_resolved", canonical=canonical)
        else:
            log.warning("source_unresolved", raw_source=raw_source)
        return canonical
