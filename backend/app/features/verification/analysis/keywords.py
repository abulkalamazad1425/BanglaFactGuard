"""Directional keyword coverage: do the CLAIM's keywords occur in the EVIDENCE?

Why not compare two keyword lists: independently extracted lists (e.g. YAKE
top-N of the headline vs. of a long article) can miss each other entirely, so
a headline that matches its own article word-for-word could score 0.

This module instead takes every content word of the claim, applies the same
normalisation/tokenisation/stemming to the evidence text, and checks
membership directly. Coverage = matched claim weight / applicable claim
weight (directional; extra evidence words never reduce it).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.core.constants import MetricState
from app.features.verification.analysis.text import (
    content_tokens,
    is_negation_token,
    is_number_token,
    is_qualifier_token,
    light_stem,
    tokenize,
)

_WEIGHT_CONTENT = 1.0
# Meaning-bearing units weigh more: dropping a negation or number changes the
# claim's truth conditions far more than dropping an adjective.
_WEIGHT_MEANING = 1.5


@dataclass
class KeywordUnit:
    text: str
    weight: float
    kind: str  # content | number | negation | qualifier

@dataclass
class KeywordCoverage:
    state: MetricState
    value: float | None
    units: list[KeywordUnit] = field(default_factory=list)
    matched: list[str] = field(default_factory=list)
    unmatched: list[str] = field(default_factory=list)
    reason: str | None = None

def extract_claim_units(text: str) -> list[KeywordUnit]:
    """Deterministic keyword units for a claim: every content word once."""
    seen: set[str] = set()
    units: list[KeywordUnit] = []
    for tok in content_tokens(text):
        key = tok if is_number_token(tok) else light_stem(tok)
        if key in seen:
            continue
        seen.add(key)
        if is_number_token(tok):
            units.append(KeywordUnit(tok, _WEIGHT_MEANING, "number"))
        elif is_negation_token(tok):
            units.append(KeywordUnit(tok, _WEIGHT_MEANING, "negation"))
        elif is_qualifier_token(tok):
            units.append(KeywordUnit(tok, _WEIGHT_MEANING, "qualifier"))
        else:
            units.append(KeywordUnit(tok, _WEIGHT_CONTENT, "content"))
    return units


def evidence_keys(evidence_text: str) -> set[str]:
    toks = tokenize(evidence_text)
    keys: set[str] = set()
    for i, tok in enumerate(toks):
        keys.add(tok)
        keys.add(light_stem(tok))
        # Compound written as two words in one text and one in the other
        # (প্রধান মন্ত্রী / প্রধানমন্ত্রী): index adjacent concatenations too.
        if i + 1 < len(toks):
            joined = tok + toks[i + 1]
            keys.add(joined)
            keys.add(light_stem(joined))
    return keys


def keyword_coverage(claim_text: str, evidence_text: str) -> KeywordCoverage:
    """Weighted fraction of the claim's keyword units found in the evidence.

    States: COMPUTED (value may be a genuine 0.0), EMPTY (claim yielded no
    applicable units), UNAVAILABLE (no evidence text / utility failure).
    """
    try:
        units = extract_claim_units(claim_text)
        if not units:
            return KeywordCoverage(
                MetricState.EMPTY, None, reason="no applicable keywords in claim text"
            )
        if not evidence_text or not evidence_text.strip():
            return KeywordCoverage(
                MetricState.UNAVAILABLE, None, units=units, reason="no evidence text"
            )
        keys = evidence_keys(evidence_text)
        matched: list[str] = []
        unmatched: list[str] = []
        matched_w = 0.0
        total_w = 0.0
        for unit in units:
            total_w += unit.weight
            probe = {unit.text, light_stem(unit.text)}
            if probe & keys:
                matched.append(unit.text)
                matched_w += unit.weight
            else:
                unmatched.append(unit.text)
        return KeywordCoverage(
            MetricState.COMPUTED,
            round(matched_w / total_w, 4),
            units=units,
            matched=matched,
            unmatched=unmatched,
        )
    except Exception as exc:  # utility failure must be distinguishable from zero
        return KeywordCoverage(
            MetricState.UNAVAILABLE, None, reason=f"keyword utility failed: {exc}"
        )
