"""
app/pipelines/stages/s08_similarity_analyzer.py
==================================================
Stage 8: Multi-Dimensional Similarity Analysis

## Responsibility

Compute four similarity dimensions between the claim and the top-ranked article:

| Dimension              | Method                          | Score |
|------------------------|---------------------------------|-------|
| semantic_similarity    | LaBSE cosine (blended h+b)     | [0,1] |
| entity_match           | Directional NER overlap         | [0,1] |
| keyword_overlap        | YAKE-weighted overlap           | [0,1] |
| numerical_consistency  | Asymmetric numeral matching     | [0,1] |

Additionally, two sub-dimension scores are pre-computed and cached on
`context.scores` for downstream use by S10 and S11:

| Sub-dimension          | Method                          | Score |
|------------------------|---------------------------------|-------|
| headline_similarity    | LaBSE cosine (headline only)    | [0,1] |
| body_similarity        | LaBSE cosine (body only)        | [0,1] |

`contradiction_score` is left as None here — it is populated in Stage 9 (NLI).

## Criticality: NON-CRITICAL
Each dimension is computed independently. Failure in one dimension
leaves its score as None; the classifier handles None scores.

## Improvement notes (v2)

1. **Pre-computed headline/body similarity**: S10 previously made a separate
   LaBSE call for headline-vs-headline. Now S08 computes both headline-only
   and body-only similarity, stores them on context.scores, and S10 reads
   them directly — eliminating the redundant inference call.

2. **Directional entity overlap**: The old symmetric intersection ratio
   was too lenient when the article contains many extra entities. Now applies
   a 0.3x penalty for article-only entities, catching cases where the article
   discusses a completely different entity set.

3. **YAKE-weighted keyword overlap**: Old Jaccard treated all keywords
   equally. Now uses YAKE relevance scores as weights so matching on
   high-importance keywords (named entities, topic terms) contributes more
   than matching on low-importance keywords (common verbs).

4. **Asymmetric numerical consistency**: Added partial credit (0.5) for
   claim numerals that have a near-match (±10%) in the article. This
   distinguishes "inflated number" from "completely fabricated number".
"""

from __future__ import annotations

import asyncio

import structlog

from app.core.constants import PipelineStageID
from app.features.verification.pipeline.context import PipelineContext
from app.features.nlp.embedding_service import EmbeddingService
from app.features.nlp.ner_service import NERService
from app.shared.utils.keyword_extractor import (
    compute_weighted_keyword_overlap,
    extract_keywords_with_scores,
    extract_headline_keywords,
)
from app.shared.utils.number_extractor import extract_numerals_set

logger = structlog.get_logger(__name__)

# Penalty weight for article-only entities in directional overlap.
# Lower values (closer to 0) make the score more lenient about extra
# entities in the article; higher values penalise them more.
_ARTICLE_EXTRA_ENTITY_PENALTY = 0.3

# Near-match tolerance for numerical consistency: a claim numeral within
# ±10% of an article numeral receives partial credit (0.5) rather than
# full penalty (0.0). This distinguishes "inflated number" from "fabricated".
_NUM_NEAR_MATCH_TOLERANCE = 0.10
_NUM_NEAR_MATCH_CREDIT = 0.5


class SimilarityAnalyzerStage:
    """
    Stage 8: Compute semantic similarity, entity match, keyword overlap,
    and numerical consistency between claim and best evidence article.

    Dependencies:
        embedding_service: LaBSE for semantic similarity.
        ner_service:       BanglaBERT NER for entity extraction.
    """

    stage_id = PipelineStageID.S08_SIMILARITY_ANALYZER

    def __init__(
        self,
        embedding_service: EmbeddingService,
        ner_service: NERService,
    ) -> None:
        self._embedder = embedding_service
        self._ner = ner_service

    async def execute(self, context: PipelineContext) -> PipelineContext:
        """
        Compute all four similarity dimensions and store in context.scores.

        Args:
            context: Pipeline context with top_article and normalized_headline set.

        Returns:
            Context with scores.semantic_similarity, scores.entity_match,
            scores.keyword_overlap, and scores.numerical_consistency populated,
            plus scores.headline_similarity and scores.body_similarity.
        """
        if not context.top_article:
            logger.debug("s08_no_top_article_skipping")
            context.record_stage_error(self.stage_id, "No ranked article available for analysis")
            return context

        article = context.top_article
        claim_headline = context.normalized_headline
        claim_body = context.normalized_body or ""
        article_title = article.title or ""
        article_body = article.body or ""

        # Full claim text for multi-field analysis
        claim_full = f"{claim_headline} {claim_body}".strip()
        article_full = f"{article_title} {article_body}".strip()

        # ------------------------------------------------------------------
        # 1. Semantic similarity — pre-compute headline-only and body-only
        #    separately, then blend for the composite score.
        #
        #    Why separate: S10 needs headline_similarity to detect headline
        #    manipulation (low headline sim + high body sim). Previously S10
        #    made a redundant LaBSE call. Now S08 pre-computes both.
        #
        #    Blending: body carries more information than headline for
        #    verification, so body_sim gets 70% weight.
        # ------------------------------------------------------------------
        headline_sim: float | None = None
        body_sim: float | None = None
        sem_sim: float | None = None

        try:
            # Compute headline-vs-headline and body-vs-body in parallel
            headline_sim_task = self._embedder.compute_similarity(
                claim_headline, article_title
            ) if article_title else asyncio.coroutine(lambda: 0.5)()

            body_sim_task = self._embedder.compute_similarity(
                claim_full, article_body
            ) if article_body else asyncio.coroutine(lambda: None)()

            headline_sim, body_sim = await asyncio.gather(
                headline_sim_task, body_sim_task
            )

            # Blend into composite semantic_similarity
            if body_sim is not None and headline_sim is not None:
                sem_sim = 0.3 * headline_sim + 0.7 * body_sim
            elif body_sim is not None:
                sem_sim = body_sim
            elif headline_sim is not None:
                sem_sim = headline_sim

            logger.debug(
                "s08_semantic_similarity",
                headline_sim=round(headline_sim, 4) if headline_sim is not None else None,
                body_sim=round(body_sim, 4) if body_sim is not None else None,
                composite=round(sem_sim, 4) if sem_sim is not None else None,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("s08_semantic_similarity_failed", error=str(exc))
            context.record_stage_error(self.stage_id, f"Semantic similarity failed: {exc}")

        # ------------------------------------------------------------------
        # 2. Entity match — directional overlap with article-extra penalty
        #
        #    Why directional: Fake news often introduces entities not in the
        #    original article. The recall component (claim entities found in
        #    article) catches "fabricated entities". The penalty component
        #    (article entities not in claim) catches "completely different
        #    article" — but with a lower weight (0.3x) since articles
        #    naturally contain more entities than headlines.
        #
        #    Also extract typed entities for S10's type-aware substitution.
        # ------------------------------------------------------------------
        entity_match: float | None = None
        try:
            # Extract both plain entities and typed entities concurrently
            (claim_entities, article_entities,
             claim_typed, article_typed) = await _gather_entities_with_types(
                self._ner, claim_full, article_full
            )

            context.claim_entities = claim_entities
            context.article_entities = article_entities
            context.claim_entity_types = claim_typed
            context.article_entity_types = article_typed

            entity_match = _compute_directional_entity_overlap(
                claim_entities, article_entities
            )
            logger.debug(
                "s08_entity_match",
                score=round(entity_match, 4),
                claim_count=len(claim_entities),
                article_count=len(article_entities),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("s08_entity_match_failed", error=str(exc))
            context.record_stage_error(self.stage_id, f"Entity match failed: {exc}")

        # ------------------------------------------------------------------
        # 3. Keyword overlap — YAKE-weighted
        #
        #    Why weighted: Jaccard over raw keyword sets treats all keywords
        #    equally. But matching on a named entity keyword ("শেখ হাসিনা")
        #    is far more informative than matching on "বলেছেন" (said).
        #    YAKE assigns relevance scores; we use them as weights.
        # ------------------------------------------------------------------
        kw_overlap: float | None = None
        try:
            claim_kws_weighted = extract_keywords_with_scores(
                claim_headline, max_ngram_size=1, num_keywords=6
            )
            article_kws_weighted = extract_keywords_with_scores(
                article_full, max_ngram_size=2, num_keywords=10
            )
            # Store plain keyword strings for backward compat
            context.claim_keywords = (
                context.claim_keywords
                or [kw for kw, _ in claim_kws_weighted]
            )
            kw_overlap = compute_weighted_keyword_overlap(
                claim_kws_weighted, article_kws_weighted
            )
            logger.debug("s08_keyword_overlap", score=round(kw_overlap, 4))
        except Exception as exc:  # noqa: BLE001
            logger.warning("s08_keyword_overlap_failed", error=str(exc))

        # ------------------------------------------------------------------
        # 4. Numerical consistency — asymmetric with near-match credit
        #
        #    Why asymmetric: Fake news typically introduces false numbers
        #    into the claim. A claim numeral absent from the article is the
        #    primary signal. But a numeral that is "close" (within ±10%)
        #    suggests inflation/deflation rather than fabrication — so it
        #    receives partial credit (0.5) rather than full penalty (0.0).
        # ------------------------------------------------------------------
        num_consistency: float | None = None
        try:
            claim_nums = extract_numerals_set(claim_full)
            article_nums = extract_numerals_set(article_full)
            context.claim_numerals = list(claim_nums)
            context.article_numerals = list(article_nums)
            num_consistency = _compute_asymmetric_numerical_consistency(
                claim_nums, article_nums
            )
            logger.debug("s08_numerical_consistency", score=round(num_consistency, 4))
        except Exception as exc:  # noqa: BLE001
            logger.warning("s08_numerical_consistency_failed", error=str(exc))

        # ------------------------------------------------------------------
        # Update context scores (merge — preserves existing values)
        # ------------------------------------------------------------------
        context.update_scores(
            semantic_similarity=sem_sim,
            headline_similarity=headline_sim,
            body_similarity=body_sim,
            entity_match=entity_match,
            keyword_overlap=kw_overlap,
            numerical_consistency=num_consistency,
        )

        logger.info(
            "s08_analysis_complete",
            semantic=round(sem_sim, 3) if sem_sim is not None else None,
            headline_sim=round(headline_sim, 3) if headline_sim is not None else None,
            body_sim=round(body_sim, 3) if body_sim is not None else None,
            entity=round(entity_match, 3) if entity_match is not None else None,
            keyword=round(kw_overlap, 3) if kw_overlap is not None else None,
            numeral=round(num_consistency, 3) if num_consistency is not None else None,
        )
        return context


# ---------------------------------------------------------------------------
# Private helper functions
# ---------------------------------------------------------------------------


async def _gather_entities_with_types(
    ner: NERService, text_a: str, text_b: str
) -> tuple[list[str], list[str], list[tuple[str, str]], list[tuple[str, str]]]:
    """
    Run both plain and typed NER on both texts concurrently.

    Returns:
        (claim_entities, article_entities, claim_typed, article_typed)
    """
    results = await asyncio.gather(
        ner.extract_entities(text_a),
        ner.extract_entities(text_b),
        ner.extract_entities_with_types(text_a),
        ner.extract_entities_with_types(text_b),
    )
    return results[0], results[1], results[2], results[3]


def _compute_directional_entity_overlap(
    claim_entities: list[str],
    article_entities: list[str],
) -> float:
    """
    Compute directional entity overlap that penalises asymmetrically.

    Recall (primary signal):
        |claim ∩ article| / |claim|
        — How many claim entities appear in the article.

    Article-extra penalty (secondary signal):
        0.3 × |article - claim| / max(|article|, 1)
        — A mild penalty when the article has many entities not in the claim,
        suggesting the retrieved article covers a different event.

    The 0.3 weight is intentionally low: articles naturally discuss more
    entities than a headline claim, so we don't want to penalise this
    too aggressively. But if the article is about a completely different
    set of entities, this penalty pulls the score down.

    Args:
        claim_entities:   Entities from the claim.
        article_entities: Entities from the article.

    Returns:
        Float in [0.0, 1.0]. 1.0 if no claim entities.
    """
    if not claim_entities:
        return 1.0

    claim_set = {e.lower().strip() for e in claim_entities if e.strip()}
    article_set = {e.lower().strip() for e in article_entities if e.strip()}

    if not claim_set:
        return 1.0

    # Primary: recall of claim entities in article
    recall = len(claim_set & article_set) / len(claim_set)

    # Secondary: mild penalty for article entities absent from claim
    if article_set:
        extra_ratio = len(article_set - claim_set) / len(article_set)
        penalty = _ARTICLE_EXTRA_ENTITY_PENALTY * extra_ratio
    else:
        penalty = 0.0

    return max(0.0, min(1.0, recall - penalty))


def _compute_asymmetric_numerical_consistency(
    claim_nums: set[str],
    article_nums: set[str],
) -> float:
    """
    Compute numerical consistency with partial credit for near-matches.

    For each claim numeral:
    - Exact match in article → 1.0 credit
    - Near match (within ±10%) → 0.5 credit (inflated/deflated number)
    - No match → 0.0 credit (fabricated number)

    Score = sum(credits) / |claim_nums|

    If claim has no numerals, returns 1.0 (nothing to verify).

    Why partial credit: Fake news often inflates or deflates real numbers
    (e.g. "10 killed" → "100 killed"). A near-match is suspicious but less
    severe than a completely fabricated number. The 0.5 credit reflects this
    graduated severity.

    Args:
        claim_nums:   Set of normalised numeral strings from the claim.
        article_nums: Set of normalised numeral strings from the article.

    Returns:
        Float in [0.0, 1.0].
    """
    if not claim_nums:
        return 1.0

    # Pre-parse article numerals for near-match comparison
    article_values: list[float] = []
    for n in article_nums:
        try:
            article_values.append(float(n.replace(",", "")))
        except ValueError:
            continue

    total_credit = 0.0
    for num_str in claim_nums:
        if num_str in article_nums:
            total_credit += 1.0  # Exact match
            continue

        # Check for near-match
        try:
            claim_val = float(num_str.replace(",", ""))
        except ValueError:
            total_credit += 0.0  # Unparseable → no credit
            continue

        near_match = any(
            abs(claim_val - av) <= _NUM_NEAR_MATCH_TOLERANCE * max(abs(claim_val), abs(av), 1e-9)
            for av in article_values
        )
        if near_match:
            total_credit += _NUM_NEAR_MATCH_CREDIT  # Near match → partial credit
        # else: total_credit += 0.0 (no match, no credit)

    return total_credit / len(claim_nums)
