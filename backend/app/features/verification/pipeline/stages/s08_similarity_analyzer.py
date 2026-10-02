from __future__ import annotations

import numpy as np
import structlog

from app.core.constants import ClaimScope, MetricState, PipelineStageID
from app.features.nlp.embedding_service import EmbeddingService
from app.features.nlp.ner_service import NERService
from app.features.verification.analysis.entities import entity_coverage
from app.features.verification.analysis.keywords import KeywordCoverage, keyword_coverage
from app.features.verification.analysis.passages import select_relevant_passages
from app.features.verification.analysis.text import chunk_text, parse_number_phrases
from app.features.verification.pipeline.context import PipelineContext
from app.features.verification.schemas import EvidencePassage, MetricDetail

logger = structlog.get_logger(__name__)

_HEADLINE_WEIGHT = 0.3
_BODY_WEIGHT = 0.7
_MAX_PASSAGES = 3
_MAX_BODY_PASSAGES = 8
_BODY_CHUNK_CHARS = 450
_MAX_CLAIM_CHUNKS = 120
_MAX_SOURCE_CHUNKS = 200
_MIN_CHUNK_CHARS_FOR_MIN = 20


class SimilarityAnalyzerStage:
    """Scope-aware component measurements.

    HEADLINE_ONLY (always for photo cards)
        headline_similarity   submitted headline vs the source TITLE
        body_similarity       NOT_APPLICABLE (null) — no body was submitted, so
                              none is computed, weighted or displayed
        passage_similarity    headline vs the most relevant source passages
                              (with surrounding sentences) — supporting
                              evidence, stored separately, never "Body Match"
        semantic_similarity   = headline_similarity

    HEADLINE_WITH_BODY (text claims that include a body)
        headline_similarity   as above
        body_similarity       submitted body chunked WITHOUT truncation and
                              aligned chunk-by-chunk against source body
                              chunks (length-weighted mean of best matches;
                              the weakest chunk is kept so one altered
                              paragraph cannot hide behind a matching title)
        semantic_similarity   0.3·headline + 0.7·body when both exist, else
                              null (a headline-only number is not presented
                              as a whole-claim similarity)

    Keyword and entity metrics are directional claim->evidence coverage; see
    `analysis/keywords.py` and `analysis/entities.py`.
    """

    stage_id = PipelineStageID.S08_SIMILARITY_ANALYZER

    def __init__(self, embedding_service: EmbeddingService, ner_service: NERService) -> None:
        self._embedder = embedding_service
        self._ner = ner_service

    async def execute(self, context: PipelineContext) -> PipelineContext:
        if not context.top_article:
            logger.debug("s08_no_top_article_skipping")
            context.record_stage_error(self.stage_id, "No ranked article available for analysis")
            return context

        article = context.top_article
        claim_headline = context.normalized_headline
        with_body = context.claim_scope == ClaimScope.HEADLINE_WITH_BODY and context.has_body
        claim_body = context.normalized_body if with_body else None
        title = article.title or ""
        art_body = article.body or ""
        metrics = context.analysis.metrics

        # ── headline vs source title ───────────────────────────────────
        headline_sim: float | None = None
        if title:
            try:
                headline_sim = max(
                    0.0, min(1.0, await self._embedder.compute_similarity(claim_headline, title))
                )
                metrics["headline_similarity"] = MetricDetail(
                    state=MetricState.COMPUTED, value=round(headline_sim, 4)
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("s08_headline_similarity_failed", error=str(exc))
                context.record_stage_error(self.stage_id, f"Headline similarity failed: {exc}")
                metrics["headline_similarity"] = MetricDetail(
                    state=MetricState.UNAVAILABLE, reason=str(exc)[:200]
                )
        else:
            metrics["headline_similarity"] = MetricDetail(
                state=MetricState.UNAVAILABLE, reason="source article has no title"
            )

        # ── relevant passages (headline-driven, with context) ───────────
        passages = select_relevant_passages(
            claim_headline, art_body, max_passages=_MAX_PASSAGES, context_window=1
        )
        context.analysis.passages = [
            EvidencePassage(
                text=p.text,
                score=round(p.score, 4),
                location="body",
                first_sentence=p.first_sentence,
                last_sentence=p.last_sentence,
            )
            for p in passages
        ]
        passage_sim: float | None = None
        if not art_body:
            metrics["passage_similarity"] = MetricDetail(
                state=MetricState.UNAVAILABLE, reason="article body was not extracted"
            )
        elif not passages:
            metrics["passage_similarity"] = MetricDetail(
                state=MetricState.EMPTY,
                reason="no source passage discusses the claim's keywords",
            )
        else:
            try:
                embs = await self._embedder.encode_batch([claim_headline] + [p.text for p in passages])
                sims = [float(np.dot(embs[0], e)) for e in embs[1:]]
                passage_sim = max(0.0, min(1.0, max(sims)))
                metrics["passage_similarity"] = MetricDetail(
                    state=MetricState.COMPUTED,
                    value=round(passage_sim, 4),
                    details={"passages": len(passages)},
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("s08_passage_similarity_failed", error=str(exc))
                metrics["passage_similarity"] = MetricDetail(
                    state=MetricState.UNAVAILABLE, reason=str(exc)[:200]
                )

        # ── submitted body vs source body (text with body only) ─────────
        body_sim: float | None = None
        if not with_body:
            metrics["body_similarity"] = MetricDetail(
                state=MetricState.NOT_APPLICABLE,
                reason="no body was submitted (headline-only claim)",
            )
        elif not art_body:
            metrics["body_similarity"] = MetricDetail(
                state=MetricState.UNAVAILABLE, reason="source article body was not extracted"
            )
        else:
            body_sim = await self._body_similarity(context, claim_body or "", art_body)

        sem_sim: float | None
        if not with_body:
            sem_sim = headline_sim
        elif headline_sim is not None and body_sim is not None:
            sem_sim = _HEADLINE_WEIGHT * headline_sim + _BODY_WEIGHT * body_sim
        else:
            sem_sim = None

        # ── keyword coverage (claim -> evidence) ───────────────────────
        evidence_relevant = " ".join([title] + [p.text for p in passages]).strip()
        kw_head = keyword_coverage(claim_headline, title)
        kw_pass = keyword_coverage(claim_headline, evidence_relevant)
        kw_body: KeywordCoverage | None = None
        if with_body:
            kw_body = keyword_coverage(claim_body or "", f"{title} {art_body}")
        for name, cov in (
            ("headline_keyword_coverage", kw_head),
            ("passage_keyword_coverage", kw_pass),
            *((("body_keyword_coverage", kw_body),) if kw_body else ()),
        ):
            metrics[name] = MetricDetail(
                state=cov.state,
                value=cov.value,
                reason=cov.reason,
                details={"matched": cov.matched, "unmatched": cov.unmatched,
                         "units": [u.to_dict() for u in cov.units]},
            )
            logger.debug(
                "s08_keyword_diagnostics",
                metric=name,
                state=cov.state.value,
                value=cov.value,
                units=[(u.text, u.weight, u.kind) for u in cov.units],
                matched=cov.matched,
                unmatched=cov.unmatched,
            )
        if not with_body:
            metrics["body_keyword_coverage"] = MetricDetail(
                state=MetricState.NOT_APPLICABLE, reason="no body was submitted"
            )
        context.claim_keywords = context.claim_keywords or [u.text for u in kw_head.units]

        # ── entity coverage ────────────────────────────────────────────
        entity_cov = await self._entity_metrics(
            context, claim_headline, claim_body, title, passages, art_body
        )

        # ── numerical consistency ──────────────────────────────────────
        num_consistency = self._numerical_consistency(
            context, claim_headline, claim_body, title, passages, art_body, with_body
        )

        context.update_scores(
            semantic_similarity=sem_sim,
            headline_similarity=headline_sim,
            body_similarity=body_sim,
            passage_similarity=passage_sim,
            entity_match=entity_cov,
            keyword_overlap=kw_head.value,
            headline_keyword_coverage=kw_head.value,
            passage_keyword_coverage=kw_pass.value,
            body_keyword_coverage=kw_body.value if kw_body else None,
            numerical_consistency=num_consistency,
        )
        logger.info(
            "s08_analysis_complete",
            scope=context.claim_scope.value,
            headline_sim=_r(headline_sim),
            body_sim=_r(body_sim),
            passage_sim=_r(passage_sim),
            semantic=_r(sem_sim),
            entity=_r(entity_cov),
            keyword=_r(kw_head.value),
            numeral=_r(num_consistency),
        )
        return context

    # ── body comparison ───────────────────────────────────────────────

    async def _body_similarity(
        self, context: PipelineContext, claim_body: str, art_body: str
    ) -> float | None:
        metrics = context.analysis.metrics
        try:
            claim_chunks, claim_trunc = chunk_text(
                claim_body, max_chars=_BODY_CHUNK_CHARS, max_chunks=_MAX_CLAIM_CHUNKS
            )
            src_chunks, _ = chunk_text(
                art_body, max_chars=_BODY_CHUNK_CHARS, max_chunks=_MAX_SOURCE_CHUNKS
            )
            if not claim_chunks or not src_chunks:
                metrics["body_similarity"] = MetricDetail(
                    state=MetricState.UNAVAILABLE, reason="no comparable text after chunking"
                )
                return None
            embs = await self._embedder.encode_batch(claim_chunks + src_chunks)
            claim_e = np.vstack(embs[: len(claim_chunks)])
            src_e = np.vstack(embs[len(claim_chunks):])
            best = np.clip((claim_e @ src_e.T).max(axis=1), 0.0, 1.0)
            lengths = np.array([len(c) for c in claim_chunks], dtype=float)
            body_sim = float((best * lengths).sum() / lengths.sum())
            long_enough = [b for b, n in zip(best, lengths) if n >= _MIN_CHUNK_CHARS_FOR_MIN]
            context.body_min_chunk_similarity = float(min(long_enough)) if long_enough else None
            context.body_complete = not claim_trunc
            metrics["body_similarity"] = MetricDetail(
                state=MetricState.COMPUTED,
                value=round(body_sim, 4),
                details={
                    "claim_chunks": len(claim_chunks),
                    "source_chunks": len(src_chunks),
                    "min_chunk_similarity": (
                        round(context.body_min_chunk_similarity, 4)
                        if context.body_min_chunk_similarity is not None
                        else None
                    ),
                    "claim_body_truncated": claim_trunc,
                },
            )
            return body_sim
        except Exception as exc:  # noqa: BLE001
            logger.warning("s08_body_similarity_failed", error=str(exc))
            context.record_stage_error(self.stage_id, f"Body similarity failed: {exc}")
            metrics["body_similarity"] = MetricDetail(
                state=MetricState.UNAVAILABLE, reason=str(exc)[:200]
            )
            return None

    # ── entities ──────────────────────────────────────────────────────

    async def _entity_metrics(
        self,
        context: PipelineContext,
        claim_headline: str,
        claim_body: str | None,
        title: str,
        passages,
        art_body: str,
    ) -> float | None:
        metrics = context.analysis.metrics
        claim_text = claim_headline if not claim_body else f"{claim_headline}\n{claim_body}"
        evidence_parts = [title] + [p.text for p in passages]
        if claim_body:
            evidence_parts += [
                p.text
                for p in select_relevant_passages(
                    claim_body, art_body, max_passages=_MAX_BODY_PASSAGES, context_window=1
                )
            ]
        evidence_text = "\n".join(p for p in evidence_parts if p)

        try:
            claim_res = await self._ner.extract_mentions(claim_text)
            ev_res = await self._ner.extract_mentions(evidence_text)
        except Exception as exc:  # noqa: BLE001
            logger.warning("s08_entity_match_failed", error=str(exc))
            context.record_stage_error(self.stage_id, f"Entity match failed: {exc}")
            metrics["entity_match"] = MetricDetail(state=MetricState.UNAVAILABLE, reason=str(exc)[:200])
            return None

        available = claim_res.available and ev_res.available
        context.ner_available = available
        context.claim_mentions = claim_res.mentions
        context.evidence_mentions = ev_res.mentions
        context.claim_entities = [m.text for m in claim_res.mentions]
        context.article_entities = [m.text for m in ev_res.mentions]
        context.claim_entity_types = [(m.text, m.type) for m in claim_res.mentions]
        context.article_entity_types = [(m.text, m.type) for m in ev_res.mentions]

        cov = entity_coverage(
            claim_res.mentions, ev_res.mentions, evidence_text, ner_available=available
        )
        metrics["entity_match"] = MetricDetail(
            state=cov.state,
            value=cov.value,
            reason=cov.reason,
            details={
                "matches": [m.to_dict() for m in cov.matches],
                "matched": cov.matched,
                "unmatched": cov.unmatched,
                "evidence_entities": [m.to_dict() for m in ev_res.mentions],
                "ner_truncated": claim_res.truncated or ev_res.truncated,
            },
        )
        logger.debug(
            "s08_entity_diagnostics",
            state=cov.state.value,
            value=cov.value,
            matched=cov.matched,
            unmatched=cov.unmatched,
        )
        return cov.value

    # ── numbers ───────────────────────────────────────────────────────

    def _numerical_consistency(
        self,
        context: PipelineContext,
        claim_headline: str,
        claim_body: str | None,
        title: str,
        passages,
        art_body: str,
        with_body: bool,
    ) -> float | None:
        metrics = context.analysis.metrics
        try:
            claim_text = claim_headline if not claim_body else f"{claim_headline}\n{claim_body}"
            evidence_text = (
                f"{title}\n{art_body}"
                if with_body
                else "\n".join([title] + [p.text for p in passages])
            )
            claim_nums = parse_number_phrases(claim_text)
            ev_nums = parse_number_phrases(evidence_text)
            context.claim_numerals = [s for _, _, s in claim_nums]
            context.article_numerals = [s for _, _, s in ev_nums]
            if not claim_nums:
                metrics["numerical_consistency"] = MetricDetail(
                    state=MetricState.NOT_APPLICABLE, reason="claim contains no numbers"
                )
                return None
            found = 0
            missing: list[str] = []
            for value, unit, surface in claim_nums:
                if any(
                    abs(v - value) < 1e-9 and (unit is None or u is None or unit == u)
                    for v, u, _ in ev_nums
                ):
                    found += 1
                else:
                    missing.append(surface)
            score = found / len(claim_nums)
            metrics["numerical_consistency"] = MetricDetail(
                state=MetricState.COMPUTED,
                value=round(score, 4),
                details={"claimed": [s for _, _, s in claim_nums], "unsupported": missing},
            )
            return score
        except Exception as exc:  # noqa: BLE001
            logger.warning("s08_numerical_consistency_failed", error=str(exc))
            metrics["numerical_consistency"] = MetricDetail(
                state=MetricState.UNAVAILABLE, reason=str(exc)[:200]
            )
            return None


def _r(v: float | None) -> float | None:
    return round(v, 3) if v is not None else None
