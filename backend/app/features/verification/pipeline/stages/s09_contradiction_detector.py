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

    stage_id = PipelineStageID.S09_CONTRADICTION_DETECTOR

    def __init__(self, nli_service: NLIService) -> None:
        self._nli = nli_service

    async def execute(self, context: PipelineContext) -> PipelineContext:
        if not context.top_article:
            logger.debug("s09_no_top_article_skipping")
            return context

        article = context.top_article
        claim_headline = context.normalized_headline
        thresholds = _SETTINGS.classification

        degraded_mode = False
        if article.body:
            premise = _select_claim_relevant_sentences(
                article.body, claim_headline, n=5
            )
        elif article.title:

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

        temperature = thresholds.nli_temperature
        if temperature != 1.0:
            nli_result = _calibrate_nli_scores(nli_result, temperature)

        if degraded_mode:
            attenuation = thresholds.nli_title_only_attenuation
            nli_result = NLIScoresSchema(
                entailment=nli_result.entailment * attenuation,
                contradiction=nli_result.contradiction * attenuation,
                neutral=1.0
                - (
                    nli_result.entailment * attenuation
                    + nli_result.contradiction * attenuation
                ),
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


_SENTENCE_SPLIT_RE = re.compile(r"(?<=[।.!?])\s+")


_TOKEN_RE = re.compile(r"[\s।.!?,;:\"'()\[\]{}\-]+")


_OVERLAP_STOPWORDS = frozenset(
    {
        "এই",
        "এ",
        "ও",
        "এবং",
        "কিন্তু",
        "তবে",
        "যে",
        "যা",
        "তা",
        "তার",
        "আর",
        "না",
        "নি",
        "হয়",
        "হয়েছে",
        "করা",
        "করে",
        "থেকে",
        "জন্য",
        "the",
        "a",
        "an",
        "is",
        "are",
        "was",
        "of",
        "in",
        "on",
        "to",
        "for",
    }
)


def _select_claim_relevant_sentences(body: str, claim_headline: str, n: int = 5) -> str:
    sentences = _SENTENCE_SPLIT_RE.split(body.strip())
    sentences = [s.strip() for s in sentences if s.strip() and len(s.strip()) > 10]

    if len(sentences) <= n:
        return " ".join(sentences)

    claim_tokens = _tokenise_for_overlap(claim_headline)
    if not claim_tokens:

        return " ".join(sentences[:n])

    scored: list[tuple[float, int, str]] = []
    for idx, sent in enumerate(sentences):
        sent_tokens = _tokenise_for_overlap(sent)
        if not sent_tokens:
            scored.append((0.0, idx, sent))
            continue
        overlap = len(claim_tokens & sent_tokens) / len(claim_tokens)
        scored.append((overlap, idx, sent))

    scored.sort(key=lambda x: (-x[0], x[1]))
    top_n = scored[:n]

    top_n.sort(key=lambda x: x[1])

    return " ".join(s for _, _, s in top_n)


def _tokenise_for_overlap(text: str) -> set[str]:
    tokens = _TOKEN_RE.split(text.lower())
    return {t for t in tokens if t and len(t) >= 2 and t not in _OVERLAP_STOPWORDS}


def _calibrate_nli_scores(
    scores: NLIScoresSchema, temperature: float
) -> NLIScoresSchema:
    if temperature <= 0:
        return scores

    eps = 1e-9
    log_e = math.log(max(scores.entailment, eps))
    log_c = math.log(max(scores.contradiction, eps))
    log_n = math.log(max(scores.neutral, eps))

    scaled_e = log_e / temperature
    scaled_c = log_c / temperature
    scaled_n = log_n / temperature

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
