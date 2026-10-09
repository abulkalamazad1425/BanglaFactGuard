from __future__ import annotations

import structlog

from app.core.constants import PipelineStageID
from app.core.exceptions import NormalizationError
from app.features.verification.pipeline.context import PipelineContext
from app.features.sources.repository import SourceRepository
from app.features.verification import source_policy
from app.shared.utils.bangla_normalizer import normalize_bangla_text
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

        resolution = await source_policy.resolve_source(context.raw_claimed_source, self.source_repo)
        if resolution.is_fallback and context.source_resolution_reason and not context.raw_claimed_source.strip():
            # The caller knows why there is no source (e.g. a photo card where
            # none was detected) - keep that more specific reason.
            resolution = source_policy.SourceResolution(
                resolution.mode, None, context.source_resolution_reason, None
            )
        context.source_resolution_reason = context.source_resolution_reason or resolution.reason

        if resolution.is_fallback:
            if not source_policy.fallback_enabled():
                # Fallback disabled: the original fail-closed behaviour.
                raise NormalizationError(
                    stage_id=self.stage_id.value,
                    message=f"Claimed source could not be resolved: {context.raw_claimed_source!r}",
                    details={"claimed_source": context.raw_claimed_source},
                )
            context.verification_mode = source_policy.VERIFIED_SOURCES
            context.source_resolution_reason = resolution.reason
            context.normalized_source = None
            context.source_config = None
            context.verified_scope = await source_policy.load_verified_scope(self.source_repo)
            log.info(
                "verification_mode_verified_sources",
                reason=resolution.reason,
                publishers=len(context.verified_scope.publishers),
            )
            context.content_hash = compute_claim_hash(
                context.normalized_headline,
                source_policy.verified_identity_key(context.verified_scope),
                context.claim_scope,
                body=context.normalized_body,
                published_date=context.published_date,
            )
            return context

        context.verification_mode = source_policy.CLAIMED_SOURCE
        context.normalized_source = resolution.canonical
        log.debug("source_resolved", canonical=resolution.canonical)

        source_record = await self.source_repo.get_by_canonical_name(
            context.normalized_source
        )
        if source_record:
            context.source_config = source_policy.source_config_for(source_record)

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
