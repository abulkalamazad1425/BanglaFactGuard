from __future__ import annotations

import structlog

from app.core.config import get_settings
from app.core.constants import (
    VERIFICATION_PIPELINE_VERSION,
    CheckState,
    ContentStatus,
    DateStatus,
    PipelineStageID,
    SourceStatus,
)
from app.core.exceptions import ClassificationError
from app.features.verification.analysis.decisions import (
    DecisionInputs,
    Metric,
    assess_correspondence,
    check_strength,
    decide_content,
    decide_date,
    decide_source,
)
from app.features.verification.pipeline.context import PipelineContext
from app.features.verification.schemas import DateAnalysis, SearchAccounting

logger = structlog.get_logger(__name__)
_SETTINGS = get_settings()


class ClassifierStage:
    """Produces the three independent dimensions — Source, Content, Date.

    SOURCE   Did the claimed outlet publish a corresponding report? Decided
             from article correspondence (headline↔title similarity plus
             lexical support) and search adequacy. Content scores play no
             part, so an altered detail — or a weak aggregate — cannot make a
             genuine original report look like a different article. An
             adequate search without a corresponding report is NOT_FOUND; a
             failed or inadequate search is INCOMPLETE.
    CONTENT  Only once the source is CONFIRMED. ALTERED requires a concrete,
             quotable discrepancy (or a validated contradiction). MATCHED
             requires positive support for every applicable material claim.
             Weak scores, neutral NLI, missing signals and checks that did
             not run are INCOMPLETE — never an automatic ALTERED, and a
             matching headline never hides an altered body.
    DATE     Claimed day vs the report's datePublished day in Asia/Dhaka,
             independent of content. Missing actual date -> INCOMPLETE; no
             claimed date -> not applicable.

    Nothing here is an overall Fake/Real/Misleading verdict; that is an
    expert-only assessment.
    """

    stage_id = PipelineStageID.S11_CLASSIFIER

    async def execute(self, context: PipelineContext) -> PipelineContext:
        t = _SETTINGS.classification
        try:
            self._record_search(context)
            context.analysis.pipeline_version = VERIFICATION_PIPELINE_VERSION
            context.analysis.claim_scope = context.claim_scope
            context.analysis.stage_errors = dict(context.stage_errors)

            inp = self._build_inputs(context)
            corr = assess_correspondence(inp, t) if context.has_evidence else None
            source_status, source_basis = decide_source(
                has_evidence=context.has_evidence,
                search_adequate=context.search_adequate,
                retrieval_failed=context.retrieval_failed,
                correspondence=corr,
            )
            context.source_status = source_status
            context.analysis.source_basis = source_basis

            if source_status != SourceStatus.CONFIRMED:
                context.content_status = None
                context.date_status = None
                context.confidence = self._negative_strength(context, source_status)
                context.reasoning = self._reason_not_confirmed(context, source_status, source_basis)
                self._log(context, source_basis)
                return context

            article = context.top_article
            flags = context.manipulation_flags
            content_status, content_basis = decide_content(
                inp, t, concrete_failures=len(flags.discrepancies)
            )
            context.content_status = content_status
            context.analysis.content_basis = content_basis

            actual_date = article.published_date if article else None
            context.date_status = decide_date(
                context.published_date, actual_date, source_confirmed=True
            )
            context.analysis.date = DateAnalysis(
                claimed_date=context.published_date,
                article_date=actual_date,
                article_published_at=article.published_at if article else None,
                provenance=article.published_date_source if article else None,
                tz_assumed=article.published_tz_assumed if article else False,
            )

            context.confidence = self._strength(context, inp)
            context.reasoning = self._reason_confirmed(context, content_basis)
            self._log(context, content_basis)
            return context
        except Exception as exc:
            raise ClassificationError(
                stage_id=self.stage_id.value,
                message=f"Classification failed: {exc}",
            ) from exc

    # ── inputs ──────────────────────────────────────────────────────────

    @staticmethod
    def _metric(context: PipelineContext, name: str) -> Metric:
        d = context.analysis.metrics.get(name)
        return Metric(d.state, d.value) if d else Metric()

    def _build_inputs(self, context: PipelineContext) -> DecisionInputs:
        m = self._metric
        states = dict(context.manipulation_flags.check_states)
        if not states and context.has_evidence:
            # S10 produced nothing: the checks did not run, which is NOT a pass.
            states = {"alteration_checks": CheckState.NOT_EVALUATED}
        return DecisionInputs(
            scope=context.claim_scope,
            headline_similarity=m(context, "headline_similarity"),
            passage_similarity=m(context, "passage_similarity"),
            headline_keyword_coverage=m(context, "headline_keyword_coverage"),
            passage_keyword_coverage=m(context, "passage_keyword_coverage"),
            body_similarity=m(context, "body_similarity"),
            body_min_chunk_similarity=context.body_min_chunk_similarity,
            body_keyword_coverage=m(context, "body_keyword_coverage"),
            body_complete=context.body_complete,
            entity_coverage=m(context, "entity_match"),
            check_states=states,
            discrepancy_count=len(context.manipulation_flags.discrepancies),
            contradiction=context.scores.contradiction_score,
            nli_premise_is_passages=context.nli_premise == "relevant_passages",
        )

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

    # ── strength / reasoning ────────────────────────────────────────────

    @staticmethod
    def _negative_strength(context: PipelineContext, status: SourceStatus) -> float:
        """NOT_FOUND strength = share of attempted search calls that completed
        (how thoroughly the absence was checked). INCOMPLETE carries none."""
        if status != SourceStatus.NOT_FOUND or context.search_attempted <= 0:
            return 0.0
        completed = context.search_success + context.search_success_empty + context.search_cached
        return round(min(1.0, completed / context.search_attempted), 3)

    @staticmethod
    def _strength(context: PipelineContext, inp: DecisionInputs) -> float:
        def v(metric: Metric) -> float | None:
            return metric.value if metric.ok else None

        values = [v(inp.headline_similarity), v(inp.headline_keyword_coverage), v(inp.passage_keyword_coverage)]
        if inp.entity_coverage.ok:
            values.append(inp.entity_coverage.value)
        if inp.body_similarity.ok:
            values.append(inp.body_similarity.value)
        return check_strength(values)

    def _reason_not_confirmed(
        self, context: PipelineContext, status: SourceStatus, basis: list[str]
    ) -> str:
        source = context.normalized_source or context.raw_claimed_source or "the claimed source"
        s = context.analysis.search
        search_line = (
            f"Search: {s.success + s.cached} call(s) returned results, {s.success_empty} completed "
            f"with no results, {s.failed} failed, {s.skipped} skipped."
            if s
            else ""
        )
        if status == SourceStatus.NOT_FOUND:
            head = (
                f"No corresponding report from {source} was found by an adequate search. "
                "Content and date were not evaluated."
            )
        else:
            head = (
                f"The check against {source} could not be completed, so no conclusion "
                "is drawn about whether the source published this report. "
                "Content and date were not evaluated."
            )
        detail = " ".join(f"{b}." for b in basis)
        return " ".join(p for p in (head, detail, search_line, f"Verdict: source {status.value}.") if p)

    def _reason_confirmed(self, context: PipelineContext, basis: list[str]) -> str:
        source = context.normalized_source or context.raw_claimed_source or "the claimed source"
        art = context.top_article
        parts = [f"A corresponding report was found on {source}" + (f": {art.title}." if art and art.title else ".")]
        flags = context.manipulation_flags

        if context.content_status == ContentStatus.ALTERED:
            quotes = "; ".join(
                f"{d.detail} (claim: \"{d.claim_text[:80]}\")" for d in flags.discrepancies[:4]
            )
            parts.append(f"The submitted content differs from the report: {quotes}.")
        elif context.content_status == ContentStatus.MATCHED:
            parts.append("The submitted content is supported by the report: " + "; ".join(basis) + ".")
        else:
            parts.append(
                "Content could not be confirmed or refuted from the available evidence — "
                + "; ".join(basis)
                + ". This is not a finding that the content was altered."
            )

        if context.date_status == DateStatus.MATCHED:
            parts.append("The claimed publication date matches the report's date.")
        elif context.date_status == DateStatus.MISMATCHED and context.analysis.date:
            d = context.analysis.date
            parts.append(
                f"The claimed publication date ({d.claimed_date}) differs from the report's "
                f"published date ({d.article_date}, Asia/Dhaka). This does not affect the content check."
            )
        elif context.date_status == DateStatus.INCOMPLETE:
            parts.append(
                "The report's own publication date could not be determined, so the claimed date "
                "could not be checked."
            )
        elif context.published_date is None:
            parts.append("No publication date was claimed, so the date check does not apply.")

        c = context.content_status.value if context.content_status else "N/A"
        d = context.date_status.value if context.date_status else "N/A"
        parts.append(f"Verdict: source CONFIRMED, content {c}, date {d}.")
        return " ".join(parts)

    def _log(self, context: PipelineContext, basis: list[str]) -> None:
        logger.info(
            "s11_verdict",
            scope=context.claim_scope.value,
            source_status=context.source_status.value if context.source_status else None,
            content_status=context.content_status.value if context.content_status else None,
            date_status=context.date_status.value if context.date_status else None,
            check_strength=context.confidence,
            basis=basis,
            search_adequate=context.search_adequate,
            search_attempted=context.search_attempted,
            search_failed=context.search_errors,
        )
