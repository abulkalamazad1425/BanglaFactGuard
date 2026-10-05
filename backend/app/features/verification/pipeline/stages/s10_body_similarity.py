"""S10 - Body similarity: four measurements, never a verdict.

Runs only when the claim carries a body. Compares the submitted body with the
selected source article's body using TF-IDF cosine, Jaccard, normalised
Levenshtein and LaBSE embedding cosine (`analysis/body_similarity.py`).
Nothing here writes `content_status`: the scores cannot produce or change a
matched / altered / contradiction verdict.
"""

from __future__ import annotations

import structlog

from app.core.constants import BodyComparisonStatus, ClaimScope, PipelineStageID, SourceStatus
from app.features.nlp.embedding_service import EmbeddingService
from app.features.verification.analysis.body_similarity import METRIC_NAMES, compare_bodies
from app.features.verification.pipeline.context import PipelineContext
from app.features.verification.schemas import BodySimilarityMetric, BodySimilarityReport

logger = structlog.get_logger(__name__)


class BodySimilarityStage:

    stage_id = PipelineStageID.S10_BODY_SIMILARITY

    def __init__(self, embedding_service: EmbeddingService) -> None:
        self._embedder = embedding_service

    async def execute(self, context: PipelineContext) -> PipelineContext:
        claim_body = context.raw_news_body if context.claim_scope == ClaimScope.HEADLINE_WITH_BODY else None
        if not (claim_body or "").strip():
            context.analysis.body_similarity = BodySimilarityReport(
                status=BodyComparisonStatus.SKIPPED,
                reason="The claim has no body, so body similarity was not computed.",
            )
            return context
        if not context.source_confirmed:
            reason = (
                "No corresponding source article was found, so there is no source body to compare with."
                if context.source_status == SourceStatus.NOT_FOUND
                else "The source search could not be completed, so there is no source body to compare with."
            )
            context.analysis.body_similarity = BodySimilarityReport(
                status=BodyComparisonStatus.UNAVAILABLE, reason=reason, claim_chars=len(claim_body.strip())
            )
            return context

        result = await compare_bodies(claim_body, context.top_article.body, self._embedder)
        context.analysis.body_similarity = BodySimilarityReport(
            status=result.status,
            reason=result.reason,
            claim_chars=result.claim_chars,
            source_chars=result.source_chars,
            **{
                name: BodySimilarityMetric(
                    available=m.available, value=m.value, raw_value=m.raw_value, reason=m.reason, details=m.details
                )
                for name, m in result.metrics.items()
                if name in METRIC_NAMES
            },
        )
        failed = [n for n, m in result.metrics.items() if not m.available]
        if failed:
            context.record_stage_error(self.stage_id, f"Unavailable body metrics: {', '.join(failed)}")
        logger.info(
            "s10_body_similarity",
            status=result.status.value,
            scores={n: m.value for n, m in result.metrics.items()},
            unavailable=failed,
        )
        return context
