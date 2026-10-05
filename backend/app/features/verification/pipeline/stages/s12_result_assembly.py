"""S12 - Result assembly: one coherent, explainable result (no I/O).

Collects the independent findings of S08-S11 into the stored result:
pipeline version and claim scope, a source-correspondence strength, the
recorded stage errors, and a plain-language reasoning that keeps the
dimensions separate (source / headline alteration / body similarity /
date). Nothing here re-decides a dimension, and no overall Fake/Real verdict
is derived - that is an expert-only assessment.
"""

from __future__ import annotations

import structlog

from app.core.constants import (
    VERIFICATION_PIPELINE_VERSION,
    BodyComparisonStatus,
    ContentStatus,
    DateStatus,
    HeadlineCheckStatus,
    PipelineStageID,
    SourceStatus,
)
from app.core.exceptions import ClassificationError
from app.features.verification.analysis.decisions import correspondence_strength
from app.features.verification.pipeline.context import PipelineContext

logger = structlog.get_logger(__name__)


class ResultAssemblyStage:

    stage_id = PipelineStageID.S12_RESULT_ASSEMBLY

    async def execute(self, context: PipelineContext) -> PipelineContext:
        try:
            if context.source_status is None:
                # S08 never ran to completion: a failed check, not a negative.
                context.source_status = SourceStatus.INCOMPLETE
                context.analysis.source_basis = context.analysis.source_basis or [
                    "the source correspondence check did not complete"
                ]
            if context.headline_check_status is None:
                context.headline_check_status = (
                    HeadlineCheckStatus.SOURCE_NOT_FOUND
                    if context.source_status == SourceStatus.NOT_FOUND
                    else HeadlineCheckStatus.SOURCE_CHECK_INCOMPLETE
                )
            if context.source_status != SourceStatus.CONFIRMED:
                context.content_status = None
                context.date_status = None

            context.analysis.pipeline_version = VERIFICATION_PIPELINE_VERSION
            context.analysis.claim_scope = context.claim_scope
            context.analysis.stage_errors = dict(context.stage_errors)
            context.confidence = self._strength(context)
            context.reasoning = self._reasoning(context)
            logger.info(
                "s12_result_assembled",
                source_status=context.source_status.value,
                headline_verdict=context.content_status.value if context.content_status else None,
                headline_check_status=context.headline_check_status.value,
                date_status=context.date_status.value if context.date_status else None,
                body_status=(
                    context.analysis.body_similarity.status.value if context.analysis.body_similarity else None
                ),
                strength=context.confidence,
            )
            return context
        except Exception as exc:
            raise ClassificationError(stage_id=self.stage_id.value, message=f"Result assembly failed: {exc}") from exc

    @staticmethod
    def _strength(context: PipelineContext) -> float:
        """CONFIRMED: mean of the correspondence measurements. NOT_FOUND:
        share of attempted search calls that completed (how thoroughly the
        absence was checked). INCOMPLETE: 0. Never a probability of truth."""
        if context.source_status == SourceStatus.CONFIRMED:
            m = context.analysis.metrics
            return correspondence_strength([
                d.value for name in ("headline_title_similarity", "title_keyword_coverage", "passage_keyword_coverage")
                if (d := m.get(name)) is not None
            ])
        if context.source_status == SourceStatus.NOT_FOUND and context.search_attempted > 0:
            completed = context.search_success + context.search_success_empty + context.search_cached
            return round(min(1.0, completed / context.search_attempted), 3)
        return 0.0

    @staticmethod
    def _reasoning(context: PipelineContext) -> str:
        source = context.normalized_source or context.raw_claimed_source or "the claimed source"
        parts: list[str] = []
        s = context.analysis.search
        if context.source_status == SourceStatus.NOT_FOUND:
            parts.append(
                f"No corresponding report from {source} was found by an adequate search. "
                "This does not establish that the claim is false. The headline and date were not compared."
            )
        elif context.source_status == SourceStatus.INCOMPLETE:
            parts.append(
                f"The check against {source} could not be completed, so no conclusion is drawn about "
                "whether the source published this report. The headline and date were not compared."
            )
        else:
            art = context.top_article
            parts.append(f"A corresponding report was found on {source}" + (f": {art.title}." if art and art.title else "."))
            ha = context.analysis.headline_alteration
            if context.content_status == ContentStatus.MATCHED:
                parts.append("Headline Alteration: matched. " + (ha.reason if ha else ""))
            elif context.content_status == ContentStatus.ALTERED:
                parts.append("Headline Alteration: altered. " + (ha.reason if ha else ""))
            else:
                parts.append("Headline Alteration: no verdict. " + (ha.reason if ha else ""))
            if context.date_status == DateStatus.MATCHED:
                parts.append("The claimed publication date matches the report's date.")
            elif context.date_status == DateStatus.MISMATCHED and context.analysis.date:
                d = context.analysis.date
                parts.append(
                    f"The claimed publication date ({d.claimed_date}) differs from the report's published date "
                    f"({d.article_date}, Asia/Dhaka). A date mismatch alone is not a false-news verdict."
                )
            elif context.date_status == DateStatus.INCOMPLETE:
                parts.append("The report's own publication date could not be determined, so the claimed date could not be checked.")
            elif context.published_date is None:
                parts.append("No publication date was claimed, so the date check does not apply.")
        body = context.analysis.body_similarity
        if body is not None and body.status == BodyComparisonStatus.COMPUTED:
            parts.append(
                "Body similarity scores were measured separately; they describe wording/meaning overlap only "
                "and are not part of any verdict."
            )
        elif body is not None and body.status == BodyComparisonStatus.UNAVAILABLE and body.reason:
            parts.append(f"Body similarity is unavailable: {body.reason}")
        if s and context.source_status != SourceStatus.CONFIRMED:
            parts.append(
                f"Search: {s.success + s.cached} call(s) returned results, {s.success_empty} completed with no "
                f"results, {s.failed} failed, {s.skipped} skipped."
            )
        return " ".join(p.strip() for p in parts if p and p.strip())
