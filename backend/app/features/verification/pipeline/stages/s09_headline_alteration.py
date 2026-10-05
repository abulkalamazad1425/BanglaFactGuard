"""S09 - Headline Alteration: the claim headline vs. the selected source TITLE.

Identical for photo cards, headline-only text claims and headline + body
claims. The source body, body passages, body similarity scores and any
body-derived NLI are never read here, so changing the source body cannot
change this verdict. See `analysis/headline_comparison.py` for the decision
procedure (exact match first; otherwise deterministic material-difference
rules plus a semantic assessment that is always run).

Output: `content_status` = MATCHED | ALTERED | None, and
`headline_check_status` explaining a missing verdict. No source found and a
failed search are kept apart (SOURCE_NOT_FOUND vs SOURCE_CHECK_INCOMPLETE).
"""

from __future__ import annotations

import structlog

from app.core.constants import HeadlineCheckStatus, PipelineStageID, SourceStatus
from app.features.verification.analysis.headline_comparison import (
    METHOD,
    HeadlineComparator,
    HeadlineComparison,
)
from app.features.verification.pipeline.context import PipelineContext
from app.features.verification.schemas import (
    HeadlineAlterationDetail,
    HeadlineDifference,
    HeadlineSemanticAssessment,
)

logger = structlog.get_logger(__name__)


class HeadlineAlterationStage:

    stage_id = PipelineStageID.S09_HEADLINE_ALTERATION

    def __init__(self, comparator: HeadlineComparator) -> None:
        self._comparator = comparator

    async def execute(self, context: PipelineContext) -> PipelineContext:
        claim_headline = (context.raw_headline or context.normalized_headline).strip()
        context.content_status = None

        if context.source_status == SourceStatus.NOT_FOUND:
            self._no_comparison(
                context, claim_headline, HeadlineCheckStatus.SOURCE_NOT_FOUND,
                "No corresponding report was found in the claimed source, so there is no title to compare with.",
            )
            return context
        if not context.source_confirmed:
            self._no_comparison(
                context, claim_headline, HeadlineCheckStatus.SOURCE_CHECK_INCOMPLETE,
                "The source search or retrieval could not be completed, so the headline was not compared. "
                "This is not a finding that the source lacks the report.",
            )
            return context

        article = context.top_article
        try:
            comparison = await self._comparator.compare(claim_headline, article.title)
        except Exception as exc:  # noqa: BLE001 - never guess a verdict
            logger.warning("s09_comparison_failed", error=str(exc))
            context.record_stage_error(self.stage_id, f"Headline comparison failed: {exc}")
            comparison = HeadlineComparison(
                HeadlineCheckStatus.MODEL_UNAVAILABLE, None,
                "The headline comparison could not be completed, so no verdict was reached.",
            )

        context.content_status = comparison.verdict
        context.headline_check_status = comparison.status
        context.analysis.headline_alteration = HeadlineAlterationDetail(
            status=comparison.status,
            verdict=comparison.verdict,
            reason=comparison.reason,
            exact_match=comparison.exact_match,
            basis=comparison.basis,
            claim_headline=claim_headline,
            source_title=article.title or None,
            source_publisher=context.normalized_source,
            source_url=article.url,
            differences=[
                HeadlineDifference(kind=d.kind, detail=d.detail, claim_text=d.claim_text, source_text=d.source_text)
                for d in comparison.differences
            ],
            semantic=(
                HeadlineSemanticAssessment(**comparison.semantic.to_dict()) if comparison.semantic else None
            ),
            ner_available=comparison.ner_available,
            method=METHOD,
        )
        if comparison.verdict is None:
            context.record_stage_error(self.stage_id, comparison.reason)
        logger.info(
            "s09_headline_alteration",
            verdict=comparison.verdict.value if comparison.verdict else None,
            status=comparison.status.value,
            exact_match=comparison.exact_match,
            basis=comparison.basis,
        )
        return context

    @staticmethod
    def _no_comparison(context: PipelineContext, claim_headline: str, status: HeadlineCheckStatus, reason: str) -> None:
        context.headline_check_status = status
        context.analysis.headline_alteration = HeadlineAlterationDetail(
            status=status, verdict=None, reason=reason, claim_headline=claim_headline,
            source_publisher=context.normalized_source, method=METHOD,
        )
