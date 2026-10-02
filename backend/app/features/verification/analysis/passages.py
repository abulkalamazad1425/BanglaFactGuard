"""Relevant-passage selection from a source article.

A headline is never compared with the whole article body: a 2,000-word article
is mostly text the headline says nothing about, so that similarity penalises an
exact, supported headline. Instead the sentences that actually discuss the
claim are selected (with surrounding context) and compared.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.features.verification.analysis.keywords import extract_claim_units, _evidence_keys
from app.features.verification.analysis.text import light_stem, split_sentences


@dataclass
class Passage:
    text: str
    score: float          # weighted claim-keyword coverage of the core sentences
    first_sentence: int   # index of first sentence (inclusive) incl. context
    last_sentence: int    # index of last sentence (inclusive) incl. context
    location: str = "body"

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "score": round(self.score, 4),
            "first_sentence": self.first_sentence,
            "last_sentence": self.last_sentence,
            "location": self.location,
        }


def select_relevant_passages(
    claim_text: str,
    article_body: str | None,
    *,
    max_passages: int = 3,
    context_window: int = 1,
    min_score: float = 0.25,
    max_chars: int = 600,
) -> list[Passage]:
    """Top sentences by claim-keyword coverage, each widened by
    `context_window` neighbouring sentences, overlapping windows merged."""
    if not article_body or not claim_text:
        return []
    sentences = split_sentences(article_body, min_len=10)
    units = extract_claim_units(claim_text)
    if not sentences or not units:
        return []
    total_w = sum(u.weight for u in units)

    scored: list[tuple[float, int]] = []
    for idx, sent in enumerate(sentences):
        keys = _evidence_keys(sent)
        w = sum(u.weight for u in units if ({u.text, light_stem(u.text)} & keys))
        scored.append((w / total_w, idx))

    ranked = sorted((s for s in scored if s[0] >= min_score), key=lambda x: (-x[0], x[1]))
    chosen: list[tuple[float, int, int]] = []  # (score, first, last)
    for score, idx in ranked:
        first, last = max(0, idx - context_window), min(len(sentences) - 1, idx + context_window)
        merged = False
        for i, (sc, f, l) in enumerate(chosen):
            if not (last < f or first > l):  # overlap -> merge
                chosen[i] = (max(sc, score), min(f, first), max(l, last))
                merged = True
                break
        if not merged:
            if len(chosen) >= max_passages:
                continue
            chosen.append((score, first, last))

    passages: list[Passage] = []
    for score, first, last in sorted(chosen, key=lambda c: -c[0]):
        text = " ".join(sentences[first : last + 1])
        if len(text) > max_chars:
            text = text[:max_chars]
        passages.append(Passage(text=text, score=score, first_sentence=first, last_sentence=last))
    return passages
