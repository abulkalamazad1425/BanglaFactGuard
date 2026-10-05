"""S08 - Source correspondence: did the claimed outlet publish THIS report?

Decides `source_status` (CONFIRMED / NOT_FOUND / INCOMPLETE) and selects the
source article every later stage compares against. It is deliberately a
different decision from headline equivalence (S09): an altered headline can
still correspond to the very report it distorts, and a report about the same
topic, person or country does not correspond merely because of that overlap
(see `decisions.assess_correspondence`).

Measurements (claim headline vs each ranked candidate, best rank first):
  headline_title_similarity  LaBSE cosine of headline vs source title
  title_keyword_coverage     share of the claim's keywords in the title
  passage_keyword_coverage   share of the claim's keywords in the title plus
                             the source passages that discuss them

The first STRONG candidate (else the first PLAUSIBLE one, else rank #1) becomes
`top_article`. A failed or inadequate search is INCOMPLETE - never NOT_FOUND.
"""

from __future__ import annotations

import structlog

from app.core.config import get_settings
from app.core.constants import MetricState, PipelineStageID, SourceStatus
from app.features.articles.schemas import RankedArticleSchema
from app.features.nlp.embedding_service import EmbeddingService
from app.features.verification.analysis.decisions import (
    Correspondence,
    CorrespondenceInputs,
    Metric,
    assess_correspondence,
    decide_source,
)
from app.features.verification.analysis.keywords import keyword_coverage
from app.features.verification.analysis.passages import select_relevant_passages
from app.features.verification.pipeline.context import PipelineContext
from app.features.verification.schemas import MetricDetail, SearchAccounting

logger = structlog.get_logger(__name__)

_MAX_PASSAGES = 3
_LEVEL_RANK = {"STRONG": 0, "PLAUSIBLE": 1, "NONE": 2, "UNKNOWN": 3}


class SourceCorrespondenceStage:

    stage_id = PipelineStageID.S08_SOURCE_CORRESPONDENCE

    def __init__(self, embedding_service: EmbeddingService) -> None:
        self._embedder = embedding_service

    async def execute(self, context: PipelineContext) -> PipelineContext:
        self._record_search(context)
        thresholds = get_settings().classification

        best: tuple[Correspondence, RankedArticleSchema, dict[str, MetricDetail]] | None = None
        for article in context.ranked_articles:
            metrics = await self._measure(context, article)
            corr = assess_correspondence(
                CorrespondenceInputs(
                    headline_title_similarity=_metric(metrics["headline_title_similarity"]),
                    title_keyword_coverage=_metric(metrics["title_keyword_coverage"]),
                    passage_keyword_coverage=_metric(metrics["passage_keyword_coverage"]),
                ),
                thresholds,
            )
            if best is None or _LEVEL_RANK[corr.level] < _LEVEL_RANK[best[0].level]:
                best = (corr, article, metrics)
            if corr.level == "STRONG":
                break

        correspondence = best[0] if best else None
        if best is not None:
            context.top_article = best[1]
            context.analysis.metrics = best[2]

        status, basis = decide_source(
            has_evidence=context.has_evidence,
            search_adequate=context.search_adequate,
            retrieval_failed=context.retrieval_failed,
            correspondence=correspondence,
        )
        context.source_status = status
        context.analysis.source_basis = basis
        logger.info(
            "s08_source_correspondence",
            source_status=status.value,
            level=correspondence.level if correspondence else None,
            candidates=len(context.ranked_articles),
            selected_url=context.top_article.url if context.top_article and status == SourceStatus.CONFIRMED else None,
            basis=basis,
        )
        return context

    async def _measure(self, context: PipelineContext, article: RankedArticleSchema) -> dict[str, MetricDetail]:
        headline = context.normalized_headline
        title = article.title or ""
        metrics: dict[str, MetricDetail] = {}

        if title:
            try:
                sim = await self._embedder.compute_similarity(headline, title)
                metrics["headline_title_similarity"] = MetricDetail(
                    state=MetricState.COMPUTED, value=round(max(0.0, min(1.0, sim)), 4)
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("s08_similarity_failed", error=str(exc))
                context.record_stage_error(self.stage_id, f"Headline/title similarity failed: {exc}")
                metrics["headline_title_similarity"] = MetricDetail(
                    state=MetricState.UNAVAILABLE, reason=str(exc)[:200]
                )
        else:
            metrics["headline_title_similarity"] = MetricDetail(
                state=MetricState.UNAVAILABLE, reason="source article has no title"
            )

        passages = select_relevant_passages(headline, article.body or "", max_passages=_MAX_PASSAGES)
        for name, evidence in (
            ("title_keyword_coverage", title),
            ("passage_keyword_coverage", " ".join([title] + [p.text for p in passages]).strip()),
        ):
            cov = keyword_coverage(headline, evidence)
            metrics[name] = MetricDetail(
                state=cov.state, value=cov.value, reason=cov.reason,
                details={"matched": cov.matched, "unmatched": cov.unmatched},
            )
        return metrics

    @staticmethod
    def _record_search(context: PipelineContext) -> None:
        context.analysis.search = SearchAccounting(
            attempted=context.search_attempted,
            success=context.search_success,
            success_empty=context.search_success_empty,
            failed=context.search_errors,
            skipped=context.search_skipped,
            cached=context.search_cached,
            adequate=context.search_adequate,
            providers=context.search_provider_outcomes,
            redirect_rejected=context.search_redirect_rejected,
        )


def _metric(detail: MetricDetail) -> Metric:
    return Metric(detail.state, detail.value)
