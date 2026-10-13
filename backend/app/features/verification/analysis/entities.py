from __future__ import annotations

from dataclasses import dataclass

from app.features.verification.analysis.text import light_stem, tokenize

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
    return tuple(light_stem(t) for t in tokenize(text))


_ALIAS_INDEX: dict[tuple[str, ...], int] = {}
for _i, _set in enumerate(_ALIAS_SETS):
    for _form in _set:
        _ALIAS_INDEX[entity_key(_form)] = _i


@dataclass(frozen=True)
class EntityMention:
    text: str
    type: str

    @property
    def key(self) -> tuple[str, ...]:
        return entity_key(self.text)

@dataclass
class EntityMatch:
    claimed: str
    type: str
    status: str
    matched_to: str | None = None

    @property
    def matched(self) -> bool:
        return self.status in {"exact", "alias", "span", "text"}

def _contains(seq: tuple[str, ...], sub: tuple[str, ...]) -> bool:
    if not sub or len(sub) > len(seq):
        return False
    return any(seq[i : i + len(sub)] == sub for i in range(len(seq) - len(sub) + 1))


def match_entity(
    claimed: EntityMention,
    evidence_mentions: list[EntityMention],
    evidence_token_keys: tuple[str, ...],
) -> EntityMatch:
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

    containing = [m for m, key in ev_keys if _contains(key, ckey) and key != ckey]
    contained = [m for m, key in ev_keys if _contains(ckey, key) and key != ckey]
    if len(ckey) >= 2 and containing:
        return EntityMatch(claimed.text, claimed.type, "span", containing[0].text)
    if len(ckey) >= 2 and any(len(m.key) >= 2 for m in contained):
        hit = next(m for m in contained if len(m.key) >= 2)
        return EntityMatch(claimed.text, claimed.type, "span", hit.text)

    if len(ckey) == 1 and containing:
        return EntityMatch(
            claimed.text,
            claimed.type,
            "ambiguous",
            ", ".join(sorted({m.text for m in containing})),
        )

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


def mentions_in_sentence(sentence: str, mentions: list[EntityMention]) -> list[EntityMention]:
    stems = tuple(light_stem(t) for t in tokenize(sentence))
    out: list[EntityMention] = []
    seen: set[tuple[str, ...]] = set()
    for m in mentions:
        if m.key and m.key not in seen and _contains(stems, m.key):
            seen.add(m.key)
            out.append(m)
    return out
