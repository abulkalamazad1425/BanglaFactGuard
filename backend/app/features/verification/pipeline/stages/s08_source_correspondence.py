from __future__ import annotations

import re
from urllib.parse import urlparse

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

        best: tuple[tuple[int, float], Correspondence, RankedArticleSchema, dict[str, MetricDetail]] | None = None
        for article in context.ranked_articles:
            for title in dict.fromkeys([article.title, *article.title_variants]):
                metrics = await self._measure(context, article, title)
                corr = assess_correspondence(_inputs(metrics), thresholds)
                sim = metrics["headline_title_similarity"].value or 0.0
                key = (_LEVEL_RANK[corr.level], -sim)
                if best is None or key < best[0]:
                    chosen = article if title == article.title else article.model_copy(update={"title": title})
                    best = (key, corr, chosen, metrics)

        correspondence = best[1] if best else None
        if best is not None:
            context.top_article = best[2]
            context.analysis.metrics = best[3]

        blocked_match = None
        if correspondence is None or correspondence.level != "STRONG":
            blocked_match = await self._blocked_match(
                context, thresholds, better_than=correspondence.level if correspondence else None
            )

        status, basis = decide_source(
            has_evidence=context.has_evidence,
            search_adequate=context.search_adequate,
            retrieval_failed=context.retrieval_failed,
            correspondence=correspondence,
            blocked_match=blocked_match,
        )
        if context.is_verified_sources_mode:
            basis = [b.replace("the claimed source", "the verified sources searched") for b in basis]
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

    async def _blocked_match(
        self, context: PipelineContext, thresholds, *, better_than: str | None
    ) -> str | None:
        floor = _LEVEL_RANK.get(better_than, _LEVEL_RANK["NONE"]) if better_than else _LEVEL_RANK["NONE"]
        failed = {_strip_amp(u) for u in context.failed_extraction_urls}
        if not failed:
            return None
        for cand in context.candidate_urls:
            if _strip_amp(cand.url) not in failed or not cand.title_snippet:
                continue
            title = _search_title(cand.title_snippet)
            if not title:
                continue
            metrics = await self._measure(context, None, title)
            level = assess_correspondence(_inputs(metrics), thresholds).level
            if level in {"STRONG", "PLAUSIBLE"} and _LEVEL_RANK[level] < floor:
                logger.info("s08_matching_result_not_retrieved", url=cand.url[:100], title=title[:80])
                return context.publisher_for_url(cand.url) or urlparse(cand.url).hostname or cand.url
        return None

    async def _measure(
        self, context: PipelineContext, article: RankedArticleSchema | None, title: str | None
    ) -> dict[str, MetricDetail]:
        headline = context.normalized_headline
        title = title or ""
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

        body = article.body if article is not None else ""
        passages = select_relevant_passages(headline, body or "", max_passages=_MAX_PASSAGES)
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


def _inputs(metrics: dict[str, MetricDetail]) -> CorrespondenceInputs:
    return CorrespondenceInputs(
        headline_title_similarity=_metric(metrics["headline_title_similarity"]),
        title_keyword_coverage=_metric(metrics["title_keyword_coverage"]),
        passage_keyword_coverage=_metric(metrics["passage_keyword_coverage"]),
    )


def _search_title(snippet: str) -> str:
    head, sep, _tail = snippet.rpartition(" - ")
    return (head if sep and head.strip() else snippet).strip()


def _strip_amp(url: str) -> str:
    return re.sub(r"/amp(/|$)", "/", url).rstrip("/")
