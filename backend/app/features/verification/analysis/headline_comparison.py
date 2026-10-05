"""Headline Alteration: the claim headline vs. the selected source TITLE only.

The same comparison runs for a photo-card headline, a headline-only text
claim and a headline + body text claim. The source article's body, its
passages, any body similarity and any body-derived NLI are never inputs.

Decision procedure
------------------
1. No title (or no headline)  -> status SOURCE_TITLE_MISSING, no verdict.
2. Exact match                -> MATCHED immediately; nothing else runs.
   Exact-match normalisation is deliberately limited (`exact_match_key`):
   Unicode NFC, zero-width characters removed, runs of whitespace collapsed
   to one space, and a single trailing sentence terminator (। . ! ?)
   removed. Names, numbers, negation, quotes and every internal punctuation
   mark are kept, so no meaningful change can become an exact match.
3. Otherwise BOTH assessments always run:
   a. deterministic material-difference rules (`material_differences.py`:
      numbers, dates, negation, modality, scope, subject-object roles,
      attribution, denial, named entities);
   b. semantic assessment with the local multilingual NLI model in both
      directions (title => headline is the decisive one) plus the LaBSE
      embedding cosine as a second, supporting signal.
4. Verdict:
   * any material difference                          -> ALTERED
   * same words in the same order (punctuation-only)  -> MATCHED
   * semantic equivalence established                 -> MATCHED
       (title entails the headline >= ENTAIL_MATCH, contradiction <=
        CONTRADICTION_MAX_FOR_MATCH, embedding cosine >= COSINE_MIN_FOR_MATCH)
   * semantic divergence established                  -> ALTERED ("main_point")
       (title contradicts the headline >= CONTRADICTION_ALTERED, or entails
        it < ENTAIL_DIVERGENT while the headline carries content the title
        does not)
   * semantic model unavailable                       -> MODEL_UNAVAILABLE, no verdict
   * otherwise                                        -> UNDETERMINED, no verdict

"No conflict was found" is never a reason for MATCHED: MATCHED always needs
an exact match, an identical word sequence, or positive semantic evidence.

Thresholds were checked against the deployed local models (mDeBERTa-v3
XNLI, LaBSE) on Bangla headline pairs: every faithful paraphrase/reordering
had title=>headline entailment >= 0.88; every meaning change had <= 0.32
except a subject-object swap (0.98), which the deterministic role rule
catches. They are NOT a validated accuracy claim.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

import numpy as np
import structlog

from app.core.constants import ContentStatus, HeadlineCheckStatus
from app.features.verification.analysis.entities import EntityMention
from app.features.verification.analysis.material_differences import (
    MaterialDifference,
    find_material_differences,
    same_word_sequence,
    unmatched_content,
)

logger = structlog.get_logger(__name__)

METHOD = "headline-title-v1"

ENTAIL_MATCH = 0.80
CONTRADICTION_MAX_FOR_MATCH = 0.20
COSINE_MIN_FOR_MATCH = 0.70
CONTRADICTION_ALTERED = 0.70
ENTAIL_DIVERGENT = 0.50
NLI_MAX_CHARS = 300  # NLIService truncates hypotheses beyond this

_ZERO_WIDTH_RE = re.compile("[​⁠﻿]")
_TRAILING_TERMINATOR_RE = re.compile(r"\s*[।.!?]$")


def exact_match_key(text: str) -> str:
    """The ONLY normalisation applied before the exact-match shortcut (see
    module docstring). Internal punctuation, quotes, digits and words are
    untouched."""
    t = unicodedata.normalize("NFC", text or "")
    t = _ZERO_WIDTH_RE.sub("", t)
    t = re.sub(r"\s+", " ", t).strip()
    return _TRAILING_TERMINATOR_RE.sub("", t).strip()


def is_exact_match(claim_headline: str, source_title: str) -> bool:
    a = exact_match_key(claim_headline)
    return bool(a) and a == exact_match_key(source_title)


@dataclass
class SemanticAssessment:
    available: bool
    entailment_title_to_claim: float | None = None
    contradiction_title_to_claim: float | None = None
    entailment_claim_to_title: float | None = None
    contradiction_claim_to_title: float | None = None
    embedding_cosine: float | None = None
    reason: str | None = None

    @property
    def equivalent(self) -> bool:
        return (
            self.available
            and (self.entailment_title_to_claim or 0.0) >= ENTAIL_MATCH
            and (self.contradiction_title_to_claim or 0.0) <= CONTRADICTION_MAX_FOR_MATCH
            and self.embedding_cosine is not None
            and self.embedding_cosine >= COSINE_MIN_FOR_MATCH
        )

    def to_dict(self) -> dict:
        def r(v: float | None) -> float | None:
            return round(v, 4) if v is not None else None

        return {
            "available": self.available,
            "entailment_title_to_claim": r(self.entailment_title_to_claim),
            "contradiction_title_to_claim": r(self.contradiction_title_to_claim),
            "entailment_claim_to_title": r(self.entailment_claim_to_title),
            "contradiction_claim_to_title": r(self.contradiction_claim_to_title),
            "embedding_cosine": r(self.embedding_cosine),
            "reason": self.reason,
        }


@dataclass
class HeadlineComparison:
    """Outcome of one headline-vs-title comparison. `verdict` is MATCHED,
    ALTERED or None; `status` explains a missing verdict."""

    status: HeadlineCheckStatus
    verdict: ContentStatus | None
    reason: str
    exact_match: bool = False
    basis: str = "none"  # exact | same_words | semantic_equivalence | material_difference | semantic_divergence | none
    differences: list[MaterialDifference] = field(default_factory=list)
    semantic: SemanticAssessment | None = None
    ner_available: bool = False


class HeadlineComparator:
    """Compares a claim headline with a source title using the already-loaded
    local NLI, embedding and NER services (no third-party API)."""

    def __init__(self, nli_service, embedding_service, ner_service=None) -> None:
        self.nli = nli_service
        self.embedder = embedding_service
        self.ner = ner_service

    async def compare(self, claim_headline: str, source_title: str | None) -> HeadlineComparison:
        headline = (claim_headline or "").strip()
        title = (source_title or "").strip()
        if not headline or not title:
            return HeadlineComparison(
                HeadlineCheckStatus.SOURCE_TITLE_MISSING, None,
                "The selected source article has no extracted title, so the headline could not be compared."
                if headline else "The claim has no headline to compare.",
            )
        if is_exact_match(headline, title):
            return HeadlineComparison(
                HeadlineCheckStatus.COMPLETED, ContentStatus.MATCHED,
                "The claim headline exactly matches the source title.",
                exact_match=True, basis="exact",
            )

        claim_mentions, source_mentions, ner_ok = await self._mentions(headline, title)
        differences = find_material_differences(
            headline, title,
            claim_mentions=claim_mentions, source_mentions=source_mentions, ner_available=ner_ok,
        )
        semantic = await self._semantic(headline, title)
        result = self._decide(headline, title, differences, semantic)
        result.ner_available = ner_ok
        logger.info(
            "headline_comparison",
            verdict=result.verdict.value if result.verdict else None,
            status=result.status.value,
            basis=result.basis,
            differences=[d.kind for d in differences],
            semantic=semantic.to_dict(),
            ner_available=ner_ok,
        )
        return result

    # ── decision ─────────────────────────────────────────────────────────

    @staticmethod
    def _decide(
        headline: str, title: str, differences: list[MaterialDifference], semantic: SemanticAssessment
    ) -> HeadlineComparison:
        if differences:
            return HeadlineComparison(
                HeadlineCheckStatus.COMPLETED, ContentStatus.ALTERED,
                " ".join(d.detail for d in differences[:3]),
                basis="material_difference", differences=differences, semantic=semantic,
            )

        if same_word_sequence(headline, title) and (
            not semantic.available or (semantic.contradiction_title_to_claim or 0.0) < CONTRADICTION_ALTERED
        ):
            return HeadlineComparison(
                HeadlineCheckStatus.COMPLETED, ContentStatus.MATCHED,
                "The claim headline uses the same words in the same order as the source title; only "
                "punctuation or spacing differs.",
                basis="same_words", semantic=semantic,
            )

        if not semantic.available:
            return HeadlineComparison(
                HeadlineCheckStatus.MODEL_UNAVAILABLE, None,
                "No material difference was found by the deterministic checks, but the semantic model "
                "needed to establish equivalence was unavailable, so no verdict was reached."
                + (f" ({semantic.reason})" if semantic.reason else ""),
                semantic=semantic,
            )

        if semantic.equivalent:
            return HeadlineComparison(
                HeadlineCheckStatus.COMPLETED, ContentStatus.MATCHED,
                f"The source title expresses the same meaning as the claim headline (title-to-headline "
                f"entailment {semantic.entailment_title_to_claim:.2f}, meaning similarity "
                f"{semantic.embedding_cosine:.2f}), and names, numbers, dates, negation and attribution agree.",
                basis="semantic_equivalence", semantic=semantic,
            )

        missing = unmatched_content(headline, title)
        contra = semantic.contradiction_title_to_claim or 0.0
        entail = semantic.entailment_title_to_claim or 0.0
        if contra >= CONTRADICTION_ALTERED or (entail < ENTAIL_DIVERGENT and missing):
            parts = []
            if missing:
                parts.append(f"the headline says {', '.join(missing[:6])}, which the source title does not")
            parts.append(
                f"the source title {'contradicts' if contra >= CONTRADICTION_ALTERED else 'does not support'} "
                f"the headline's main point (title-to-headline entailment {entail:.2f}, contradiction {contra:.2f})"
            )
            detail = "The main statement differs: " + "; ".join(parts) + "."
            return HeadlineComparison(
                HeadlineCheckStatus.COMPLETED, ContentStatus.ALTERED, detail,
                basis="semantic_divergence",
                differences=[MaterialDifference("main_point", detail, headline, title,
                                                {"unmatched": ", ".join(missing[:6])})],
                semantic=semantic,
            )

        return HeadlineComparison(
            HeadlineCheckStatus.UNDETERMINED, None,
            f"Neither a meaningful difference nor an equivalent meaning could be established "
            f"(title-to-headline entailment {entail:.2f}, contradiction {contra:.2f}); no verdict was reached.",
            semantic=semantic,
        )

    # ── model calls ──────────────────────────────────────────────────────

    async def _semantic(self, headline: str, title: str) -> SemanticAssessment:
        if self.nli is None:
            return SemanticAssessment(False, reason="NLI service is not configured")
        if len(headline) > NLI_MAX_CHARS or len(title) > NLI_MAX_CHARS:
            return SemanticAssessment(False, reason="headline or title is too long for the NLI model")
        try:
            fwd = await self.nli.predict(premise=title, hypothesis=headline)
            bwd = await self.nli.predict(premise=headline, hypothesis=title)
        except Exception as exc:  # noqa: BLE001
            logger.warning("headline_nli_failed", error=str(exc))
            fwd = bwd = None
        if fwd is None:
            return SemanticAssessment(False, reason="NLI model returned no prediction")
        cosine: float | None = None
        try:
            vecs = await self.embedder.encode_batch([headline, title])
            cosine = float(np.dot(vecs[0], vecs[1]))
            if not np.isfinite(cosine):
                cosine = None
        except Exception as exc:  # noqa: BLE001
            logger.warning("headline_embedding_failed", error=str(exc))
        return SemanticAssessment(
            True,
            entailment_title_to_claim=float(fwd.entailment),
            contradiction_title_to_claim=float(fwd.contradiction),
            entailment_claim_to_title=float(bwd.entailment) if bwd else None,
            contradiction_claim_to_title=float(bwd.contradiction) if bwd else None,
            embedding_cosine=cosine,
            reason=None if cosine is not None else "embedding similarity unavailable",
        )

    async def _mentions(self, headline: str, title: str) -> tuple[list[EntityMention], list[EntityMention], bool]:
        if self.ner is None:
            return [], [], False
        try:
            c = await self.ner.extract_mentions(headline)
            s = await self.ner.extract_mentions(title)
        except Exception as exc:  # noqa: BLE001
            logger.warning("headline_ner_failed", error=str(exc))
            return [], [], False
        ok = bool(c.available and s.available)
        return (c.mentions if ok else []), (s.mentions if ok else []), ok
