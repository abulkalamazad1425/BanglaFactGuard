"""Claim-entity coverage and conservative entity matching.

Coverage is DIRECTIONAL: it asks whether the entities the claim names are
present in the source evidence. Extra people/places/organisations in a long
source article are not evidence that a headline was altered, so — unlike the
helper this replaces — there is no penalty for evidence-only entities.

Matching is deliberately conservative so different people are never merged:
exact normalised key, a small curated alias table, unambiguous multi-token
span containment, or literal presence in the evidence text. A single shared
surname is reported as *ambiguous*, not matched.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.core.constants import MetricState
from app.features.verification.analysis.text import light_stem, tokenize

# Equivalence classes of surface forms. Normalised at import with the same
# pipeline as the compared text. Intentionally small and curated.
_ALIAS_SETS: list[set[str]] = [
    {"ঢাকা", "dhaka"},
    {"বাংলাদেশ", "bangladesh"},
    {"ভারত", "ইন্ডিয়া", "india"},
    {"যুক্তরাষ্ট্র", "মার্কিন যুক্তরাষ্ট্র", "আমেরিকা", "usa", "us"},
    {"জাতিসংঘ", "united nations", "un"},
    {"বিএনপি", "বাংলাদেশ জাতীয়তাবাদী দল", "bnp"},
    {"আওয়ামী লীগ", "আওয়ামী লীগ", "awami league"},
    {"চট্টগ্রাম", "চিটাগাং", "chittagong"},
    {"সিলেট", "sylhet"},
    {"রাজশাহী", "rajshahi"},
]


def entity_key(text: str) -> tuple[str, ...]:
    """Normalised, stemmed token tuple used for every entity comparison."""
    return tuple(light_stem(t) for t in tokenize(text))


_ALIAS_INDEX: dict[tuple[str, ...], int] = {}
for _i, _set in enumerate(_ALIAS_SETS):
    for _form in _set:
        _ALIAS_INDEX[entity_key(_form)] = _i


@dataclass(frozen=True)
class EntityMention:
    text: str
    type: str  # PER | LOC | ORG

    @property
    def key(self) -> tuple[str, ...]:
        return entity_key(self.text)

    def to_dict(self) -> dict:
        return {"text": self.text, "type": self.type}


@dataclass
class EntityMatch:
    claimed: str
    type: str
    status: str  # exact | alias | span | text | ambiguous | unmatched
    matched_to: str | None = None

    @property
    def matched(self) -> bool:
        return self.status in {"exact", "alias", "span", "text"}

    def to_dict(self) -> dict:
        return {
            "claimed": self.claimed,
            "type": self.type,
            "status": self.status,
            "matched_to": self.matched_to,
        }


@dataclass
class EntityCoverage:
    state: MetricState
    value: float | None
    matches: list[EntityMatch] = field(default_factory=list)
    reason: str | None = None

    @property
    def matched(self) -> list[str]:
        return [m.claimed for m in self.matches if m.matched]

    @property
    def unmatched(self) -> list[str]:
        return [m.claimed for m in self.matches if not m.matched]

    def to_dict(self) -> dict:
        return {
            "state": self.state.value,
            "value": self.value,
            "matches": [m.to_dict() for m in self.matches],
            "matched": self.matched,
            "unmatched": self.unmatched,
            "reason": self.reason,
        }


def _contains(seq: tuple[str, ...], sub: tuple[str, ...]) -> bool:
    if not sub or len(sub) > len(seq):
        return False
    return any(seq[i : i + len(sub)] == sub for i in range(len(seq) - len(sub) + 1))


def match_entity(
    claimed: EntityMention,
    evidence_mentions: list[EntityMention],
    evidence_token_keys: tuple[str, ...],
) -> EntityMatch:
    """Match one claimed entity against evidence entities and evidence text."""
    ckey = claimed.key
    if not ckey:
        return EntityMatch(claimed.text, claimed.type, "unmatched")

    ev_keys = [(m, m.key) for m in evidence_mentions if m.key]

    for m, key in ev_keys:
        if key == ckey:
            return EntityMatch(claimed.text, claimed.type, "exact", m.text)

    alias_id = _ALIAS_INDEX.get(ckey)
    if alias_id is not None:
        for m, key in ev_keys:
            if _ALIAS_INDEX.get(key) == alias_id:
                return EntityMatch(claimed.text, claimed.type, "alias", m.text)
        if any(_ALIAS_INDEX.get(evk) == alias_id for evk in _windows(evidence_token_keys, 3)):
            return EntityMatch(claimed.text, claimed.type, "alias", None)

    # Span containment between entity mentions.
    containing = [m for m, key in ev_keys if _contains(key, ckey) and key != ckey]
    contained = [m for m, key in ev_keys if _contains(ckey, key) and key != ckey]
    if len(ckey) >= 2 and containing:
        return EntityMatch(claimed.text, claimed.type, "span", containing[0].text)
    if len(ckey) >= 2 and any(len(m.key) >= 2 for m in contained):
        hit = next(m for m in contained if len(m.key) >= 2)
        return EntityMatch(claimed.text, claimed.type, "span", hit.text)

    # A bare shared token (e.g. a surname) that only occurs inside longer,
    # distinct entities could name any of them: ambiguous, never matched.
    if len(ckey) == 1 and containing:
        return EntityMatch(
            claimed.text,
            claimed.type,
            "ambiguous",
            ", ".join(sorted({m.text for m in containing})),
        )

    # Literal presence of the claimed token sequence in the evidence text.
    if _contains(evidence_token_keys, ckey):
        return EntityMatch(claimed.text, claimed.type, "text", None)

    if len(ckey) >= 2 and contained:
        return EntityMatch(
            claimed.text,
            claimed.type,
            "ambiguous",
            ", ".join(sorted({m.text for m in (containing or contained)})),
        )
    return EntityMatch(claimed.text, claimed.type, "unmatched")


def _windows(tokens: tuple[str, ...], max_n: int):
    for n in range(1, max_n + 1):
        for i in range(len(tokens) - n + 1):
            yield tokens[i : i + n]


def entity_coverage(
    claim_mentions: list[EntityMention],
    evidence_mentions: list[EntityMention],
    evidence_text: str,
    *,
    ner_available: bool,
) -> EntityCoverage:
    """Fraction of claimed entities present in the evidence.

    UNAVAILABLE when NER could not run (never 0 and never passed);
    NOT_APPLICABLE when the claim names no entities (never an artificial 100%).
    """
    if not ner_available:
        return EntityCoverage(MetricState.UNAVAILABLE, None, reason="NER unavailable")

    seen: set[tuple[str, ...]] = set()
    unique: list[EntityMention] = []
    for m in claim_mentions:
        if m.key and m.key not in seen:
            seen.add(m.key)
            unique.append(m)
    if not unique:
        return EntityCoverage(
            MetricState.NOT_APPLICABLE, None, reason="no claim entities detected"
        )

    ev_tokens = tuple(light_stem(t) for t in tokenize(evidence_text))
    matches = [match_entity(m, evidence_mentions, ev_tokens) for m in unique]
    matched = sum(1 for m in matches if m.matched)
    return EntityCoverage(
        MetricState.COMPUTED, round(matched / len(matches), 4), matches=matches
    )


# ── grammatical role (surface case marking) ──────────────────────────────

def detect_role(sentence: str, mention_text: str) -> str:
    """Coarse grammatical role from Bangla case marking on the mention's last
    token in `sentence`: SUBJECT (unmarked/nominative), OBJECT (-কে),
    POSSESSOR (-র/-ের/-দের), LOCATIVE (-তে/-য়/-ে), AGENT (দ্বারা/কর্তৃক),
    SOURCE (থেকে), or UNKNOWN when the mention is not found.

    A *role* is not an entity *type*: two PER mentions can hold different
    roles, so substitution checks compare (type, role) together.
    """
    toks = tokenize(sentence)
    mkey = entity_key(mention_text)
    if not mkey:
        return "UNKNOWN"
    stems = [light_stem(t) for t in toks]
    for i in range(len(stems) - len(mkey) + 1):
        if tuple(stems[i : i + len(mkey)]) == mkey:
            last = i + len(mkey) - 1
            raw = toks[last]
            nxt = toks[last + 1] if last + 1 < len(toks) else ""
            if nxt in {"দ্বারা", "কর্তৃক"}:
                return "AGENT"
            if nxt == "থেকে":
                return "SOURCE"
            if raw.endswith("কে"):
                return "OBJECT"
            if raw.endswith(("দের", "ের")) or (raw.endswith("র") and len(raw) > 3 and raw[-2] == "া"):
                return "POSSESSOR"
            if raw.endswith(("তে", "ায়")):
                return "LOCATIVE"
            return "SUBJECT"
    return "UNKNOWN"


def mentions_in_sentence(sentence: str, mentions: list[EntityMention]) -> list[EntityMention]:
    """Mentions whose normalised token sequence occurs in `sentence`."""
    stems = tuple(light_stem(t) for t in tokenize(sentence))
    out: list[EntityMention] = []
    seen: set[tuple[str, ...]] = set()
    for m in mentions:
        if m.key and m.key not in seen and _contains(stems, m.key):
            seen.add(m.key)
            out.append(m)
    return out
