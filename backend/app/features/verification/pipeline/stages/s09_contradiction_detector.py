"""
app/pipelines/stages/s09_contradiction_detector.py
====================================================
Stage 9: Contradiction Detection (NLI)

## Responsibility

Run the NLI cross-encoder on (article_body, claim_headline) to obtain
the entailment/contradiction/neutral probability triple, then write:

  - `context.nli_scores`                    → full NLI triple
  - `context.scores.contradiction_score`    → NLI contradiction probability

## Premise/Hypothesis construction

Premise:    First 5 sentences of the top-ranked article body.
Hypothesis: Claim headline.

Using the article as premise and claim as hypothesis aligns with standard
NLI convention for fact-checking (article = ground truth; claim = assertion).

If the article body is absent, the article title is used as premise
(degraded accuracy, but avoids skipping the stage entirely).

## Criticality: NON-CRITICAL
NLI failure → contradiction_score = None → classifier uses conservative default.
"""

from __future__ import annotations

import structlog

from app.core.constants import PipelineStageID
from app.features.verification.pipeline.context import PipelineContext
from app.features.nlp.nli_service import NLIService
from app.shared.utils.text_cleaner import extract_first_n_sentences

logger = structlog.get_logger(__name__)


class ContradictionDetectorStage:
    """
    Stage 9: Run DeBERTa NLI to detect contradiction between claim and article.

    Dependencies:
        nli_service: DeBERTa-v3 NLI cross-encoder service.
    """

    stage_id = PipelineStageID.S09_CONTRADICTION_DETECTOR

    def __init__(self, nli_service: NLIService) -> None:
        self._nli = nli_service

    async def execute(self, context: PipelineContext) -> PipelineContext:
        """
        Run NLI inference and populate nli_scores + contradiction_score.

        Args:
            context: Pipeline context with top_article and normalized_headline set.

        Returns:
            Context with nli_scores and scores.contradiction_score populated.
        """
        if not context.top_article:
            logger.debug("s09_no_top_article_skipping")
            return context

        article = context.top_article
        claim_headline = context.normalized_headline

        # Build premise from article (prefer body, fall back to title)
        if article.body:
            premise = extract_first_n_sentences(article.body, n=5)
        elif article.title:
            premise = article.title
        else:
            logger.debug("s09_no_article_content_skipping")
            context.record_stage_error(self.stage_id, "No article content for NLI")
            return context

        logger.debug(
            "s09_running_nli",
            premise_len=len(premise),
            hypothesis_len=len(claim_headline),
        )

        nli_result = await self._nli.predict(
            premise=premise,
            hypothesis=claim_headline,
        )

        if nli_result is None:
            logger.warning("s09_nli_returned_none")
            context.record_stage_error(self.stage_id, "NLI inference returned None")
            return context

        context.nli_scores = nli_result
        context.update_scores(contradiction_score=nli_result.contradiction)

        logger.info(
            "s09_nli_complete",
            entailment=round(nli_result.entailment, 3),
            contradiction=round(nli_result.contradiction, 3),
            neutral=round(nli_result.neutral, 3),
        )
        return context

