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

Premise:    Up to 5 most claim-relevant sentences from the top-ranked article body.
Hypothesis: Claim headline.

Using the article as premise and claim as hypothesis aligns with standard
NLI convention for fact-checking (article = ground truth; claim = assertion).

If the article body is absent, the article title is used as premise
(degraded accuracy — NLI scores are attenuated by a configurable factor).

## Improvement notes (v2)

1. **Claim-relevant sentence selection**: Instead of naively taking the
   first 5 sentences (which may be irrelevant preamble), we score each
   sentence by token overlap with the claim headline and select the top-5.
   This ensures the NLI model receives the most pertinent content.

2. **Degraded-mode flagging**: When the article body is absent, NLI scores
   are attenuated by `nli_title_only_attenuation` (default 0.6) and a stage
   error is recorded. This prevents overconfident contradiction detection
   from title-only premises.

3. **NLI temperature calibration**: Raw DeBERTa probabilities are often
   overconfident (e.g. 0.52 contradiction triggers the S11 soft penalty).
   Temperature scaling flattens the distribution to reduce false positives
   at boundary thresholds.

## Criticality: NON-CRITICAL
NLI failure → contradiction_score = None → classifier uses conservative default.
"""

from __future__ import annotations

import math
import re

import structlog

from app.core.config import get_settings
from app.core.constants import PipelineStageID
from app.features.verification.pipeline.context import PipelineContext
from app.features.verification.schemas import NLIScoresSchema
from app.features.nlp.nli_service import NLIService

logger = structlog.get_logger(__name__)
_SETTINGS = get_settings()


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
        thresholds = _SETTINGS.classification

        # Build premise from article (prefer body with claim-relevant selection)
        degraded_mode = False
        if article.body:
            premise = _select_claim_relevant_sentences(
                article.body, claim_headline, n=5
            )
        elif article.title:
            # Degraded mode: title-only premise produces unreliable NLI.
            # Flag this and attenuate scores downstream.
            premise = article.title
            degraded_mode = True
            context.record_stage_error(
                self.stage_id,
                "Article body absent — using title-only premise (degraded NLI accuracy)",
            )
            logger.warning("s09_degraded_mode_title_only")
        else:
            logger.debug("s09_no_article_content_skipping")
            context.record_stage_error(self.stage_id, "No article content for NLI")
            return context

        logger.debug(
            "s09_running_nli",
            premise_len=len(premise),
            hypothesis_len=len(claim_headline),
            degraded_mode=degraded_mode,
        )

        nli_result = await self._nli.predict(
            premise=premise,
            hypothesis=claim_headline,
        )

        if nli_result is None:
            logger.warning("s09_nli_returned_none")
            context.record_stage_error(self.stage_id, "NLI inference returned None")
            return context

        # Apply temperature calibration to flatten overconfident predictions.
        # DeBERTa often produces sharp distributions (e.g. 0.52 contradiction)
        # that barely cross the S11 soft-penalty threshold of 0.5. Temperature
        # scaling with T > 1.0 smooths these borderline cases.
        temperature = thresholds.nli_temperature
        if temperature != 1.0:
            nli_result = _calibrate_nli_scores(nli_result, temperature)

        # In degraded mode (title-only premise), attenuate NLI scores to
        # express lower confidence. A title-only NLI result is inherently
        # less reliable because titles are short and may not contain enough
        # context for meaningful entailment/contradiction judgements.
        if degraded_mode:
            attenuation = thresholds.nli_title_only_attenuation
            nli_result = NLIScoresSchema(
                entailment=nli_result.entailment * attenuation,
                contradiction=nli_result.contradiction * attenuation,
                # Redistribute attenuated mass to neutral (the "uncertain" class)
                neutral=1.0 - (nli_result.entailment * attenuation
                               + nli_result.contradiction * attenuation),
            )

        context.nli_scores = nli_result
        context.update_scores(contradiction_score=nli_result.contradiction)

        logger.info(
            "s09_nli_complete",
            entailment=round(nli_result.entailment, 3),
            contradiction=round(nli_result.contradiction, 3),
            neutral=round(nli_result.neutral, 3),
            degraded=degraded_mode,
        )
        return context


# ---------------------------------------------------------------------------
# Private helper functions
# ---------------------------------------------------------------------------

# Sentence-splitting regex: split on Bangla danda, period, !, or ?
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[।.!?])\s+")

# Simple tokenizer for overlap scoring (split on whitespace and punctuation)
_TOKEN_RE = re.compile(r"[\s।.!?,;:\"'()\[\]{}\-]+")

# Bangla stopwords to exclude from overlap scoring (subset for speed)
_OVERLAP_STOPWORDS = frozenset({
    "এই", "এ", "ও", "এবং", "কিন্তু", "তবে", "যে", "যা", "তা", "তার",
    "আর", "না", "নি", "হয়", "হয়েছে", "করা", "করে", "থেকে", "জন্য",
    "the", "a", "an", "is", "are", "was", "of", "in", "on", "to", "for",
})


def _select_claim_relevant_sentences(
    body: str, claim_headline: str, n: int = 5
) -> str:
    """
    Select the N most claim-relevant sentences from the article body.

    Strategy: Score each sentence by word-level intersection with the claim
    headline (after stopword removal). Take the top-N by score. If scoring
    fails or produces no results, fall back to the first N sentences.

    Why not first-N: News articles often start with a byline, date, or
    generic lede that doesn't contain the specific claims being verified.
    Selecting claim-relevant sentences gives the NLI model more targeted
    evidence to reason over, producing more accurate contradiction scores.

    Args:
        body:           Full article body text.
        claim_headline: The normalised claim headline.
        n:              Number of sentences to select.

    Returns:
        Up to N sentences joined into a single string.
    """
    sentences = _SENTENCE_SPLIT_RE.split(body.strip())
    sentences = [s.strip() for s in sentences if s.strip() and len(s.strip()) > 10]

    if len(sentences) <= n:
        return " ".join(sentences)

    # Tokenise the claim headline for overlap scoring
    claim_tokens = _tokenise_for_overlap(claim_headline)
    if not claim_tokens:
        # Can't score — fall back to first N
        return " ".join(sentences[:n])

    # Score each sentence by overlap with claim tokens
    scored: list[tuple[float, int, str]] = []
    for idx, sent in enumerate(sentences):
        sent_tokens = _tokenise_for_overlap(sent)
        if not sent_tokens:
            scored.append((0.0, idx, sent))
            continue
        overlap = len(claim_tokens & sent_tokens) / len(claim_tokens)
        scored.append((overlap, idx, sent))

    # Sort by overlap score descending, break ties by original position
    scored.sort(key=lambda x: (-x[0], x[1]))
    top_n = scored[:n]

    # Re-sort by original position to preserve narrative flow
    top_n.sort(key=lambda x: x[1])

    return " ".join(s for _, _, s in top_n)


def _tokenise_for_overlap(text: str) -> set[str]:
    """Tokenise text into a set of lowercase tokens, excluding stopwords."""
    tokens = _TOKEN_RE.split(text.lower())
    return {t for t in tokens if t and len(t) >= 2 and t not in _OVERLAP_STOPWORDS}


def _calibrate_nli_scores(
    scores: NLIScoresSchema, temperature: float
) -> NLIScoresSchema:
    """
    Apply temperature scaling to NLI probability outputs.

    Temperature > 1.0 flattens overconfident distributions. This is a
    standard calibration technique (Guo et al., 2017 "On Calibration of
    Modern Neural Networks") applied post-hoc to the model's softmax output.

    Since we receive probabilities (not logits), we:
    1. Convert back to log-space: log(p)
    2. Divide by temperature: log(p) / T
    3. Apply softmax to get calibrated probabilities

    Args:
        scores:      Raw NLI probability triple.
        temperature: Scaling factor (> 1.0 flattens, < 1.0 sharpens).

    Returns:
        Calibrated NLIScoresSchema with probabilities summing to 1.0.
    """
    if temperature <= 0:
        return scores

    # Convert probabilities to log-space, clamping to avoid log(0)
    eps = 1e-9
    log_e = math.log(max(scores.entailment, eps))
    log_c = math.log(max(scores.contradiction, eps))
    log_n = math.log(max(scores.neutral, eps))

    # Scale by temperature
    scaled_e = log_e / temperature
    scaled_c = log_c / temperature
    scaled_n = log_n / temperature

    # Softmax to get calibrated probabilities
    max_val = max(scaled_e, scaled_c, scaled_n)
    exp_e = math.exp(scaled_e - max_val)
    exp_c = math.exp(scaled_c - max_val)
    exp_n = math.exp(scaled_n - max_val)
    total = exp_e + exp_c + exp_n

    return NLIScoresSchema(
        entailment=exp_e / total,
        contradiction=exp_c / total,
        neutral=exp_n / total,
    )
