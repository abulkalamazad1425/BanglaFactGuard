"""Evidence-backed discrepancy checks between a claim and source evidence.

Each check compares a claim sentence with the source sentence(s) that
*discuss the same thing* (sentence alignment, see `align_sentences`), and
reports an explicit CheckState:

  PASSED          the check ran and found no concrete discrepancy
  FAILED          the check found at least one concrete discrepancy
                  (listed, with the claim and evidence text that disagree)
  NOT_EVALUATED   the check could not run (no aligned evidence, NER down, the
                  claimed number is unsupported but not contradicted…)
  NOT_APPLICABLE  nothing to check for this claim (no numbers, no body …)

Low similarity or low coverage never produces FAILED here — only a concrete,
quotable disagreement does.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.core.constants import CheckState
from app.features.verification.analysis.entities import (
    EntityMention,
    detect_role,
    match_entity,
    mentions_in_sentence,
)
from app.features.verification.analysis.keywords import _evidence_keys, extract_claim_units
from app.features.verification.analysis.text import (
    QUALIFIER_GROUPS,
    STOPWORDS,
    is_negation_token,
    light_stem,
    parse_number_phrases,
    split_sentences,
    tokenize,
)

ALIGN_MIN_STRENGTH = 0.5
_TIE_BAND = 0.1

CHECK_NAMES = ("numbers", "negation", "entities", "scope", "attribution", "modality")


@dataclass
class Discrepancy:
    kind: str  # numbers | negation | entity_substitution | entity_role | scope | attribution | modality
    claim_text: str
    evidence_text: str | None
    detail: str
    part: str = "headline"  # headline | body
    meta: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "claim_text": self.claim_text,
            "evidence_text": self.evidence_text,
            "detail": self.detail,
            "part": self.part,
        }


@dataclass
class CheckResult:
    state: CheckState
    discrepancies: list[Discrepancy] = field(default_factory=list)
    note: str | None = None


@dataclass
class ClaimSentence:
    text: str
    part: str  # headline | body


@dataclass
class EvidenceSentence:
    text: str
    location: str  # title | body


@dataclass
class Alignment:
    claim: ClaimSentence
    evidence: list[tuple[EvidenceSentence, float]]  # best first; empty = unaligned

    @property
    def aligned(self) -> bool:
        return bool(self.evidence)


# ── alignment ─────────────────────────────────────────────────────────────

def _alignment_strength(claim_units, evidence_sentence: str) -> float:
    """Weighted coverage of the claim's *content* words only. Numbers,
    negations and qualifiers are excluded on purpose so that an altered
    number or a flipped negation cannot hide the fact that this evidence
    sentence is about the same thing."""
    content = [u for u in claim_units if u.kind == "content"]
    if not content:
        return 0.0
    keys = _evidence_keys(evidence_sentence)
    total = sum(u.weight for u in content)
    hit = sum(u.weight for u in content if ({u.text, light_stem(u.text)} & keys))
    return hit / total


def align_sentences(
    claim_sentences: list[ClaimSentence],
    evidence_sentences: list[EvidenceSentence],
    *,
    min_strength: float = ALIGN_MIN_STRENGTH,
) -> list[Alignment]:
    out: list[Alignment] = []
    for cs in claim_sentences:
        units = extract_claim_units(cs.text)
        scored = [
            (es, _alignment_strength(units, es.text)) for es in evidence_sentences
        ]
        scored = [(es, s) for es, s in scored if s >= min_strength]
        # Title wins ties: it is the source's own statement of the story.
        scored.sort(key=lambda x: (-x[1], 0 if x[0].location == "title" else 1))
        if scored:
            best = scored[0][1]
            scored = [(es, s) for es, s in scored if s >= best - _TIE_BAND][:3]
        out.append(Alignment(cs, scored))
    return out


# ── per-sentence feature extraction ───────────────────────────────────────

_COMPLETED_WORDS = frozenset(
    {"হলো", "হল", "করল", "দিল", "গেল", "ঘটল", "বলল", "গিয়েছে", "হয়েছিল", "মারা", "পাস"}
)
_PLAN_WORDS = frozenset(
    {
        "পারে", "পারেন", "সম্ভাবনা", "আশঙ্কা", "পরিকল্পনা", "প্রস্তাব", "উদ্যোগ",
        "সম্ভবত", "নাকি", "বিবেচনা", "চিন্তা", "ভাবছে", "ভাবছেন", "চায়", "চান",
        "সম্ভাব্য", "পরিকল্পনায়", "প্রস্তুতি",
    }
)
_ATTRIBUTION_VERBS = frozenset(
    {
        "বলেছেন", "বলেছে", "বলেন", "বলল", "বললেন", "বলছেন", "জানিয়েছেন", "জানিয়েছে",
        "জানান", "জানায়", "দাবি", "অভিযোগ", "ঘোষণা", "বলেছিলেন", "জানিয়েছিলেন",
    }
)
_CONFLICTS = (("UNIVERSAL", "PARTIAL"), ("LOWER_BOUND", "UPPER_BOUND"))


def _is_completed(tok: str) -> bool:
    if tok in _COMPLETED_WORDS:
        return True
    return len(tok) >= 5 and tok.endswith(("েছে", "েছেন", "েছিল", "েছিলেন", "লেন"))


def _is_future(tok: str) -> bool:
    return len(tok) >= 4 and tok.endswith(("বে", "বেন"))


def modality(sentence: str) -> str:
    """COMPLETED | NOT_COMPLETED (possible, planned, future) | UNKNOWN."""
    toks = tokenize(sentence)
    if any(t in _PLAN_WORDS for t in toks) or any(_is_future(t) for t in toks):
        return "NOT_COMPLETED"
    if any(_is_completed(t) for t in toks):
        return "COMPLETED"
    return "UNKNOWN"


def is_negated(sentence: str) -> bool:
    return any(is_negation_token(t) for t in tokenize(sentence))


def qualifier_groups(sentence: str) -> set[str]:
    toks = set(tokenize(sentence))
    return {g for g, words in QUALIFIER_GROUPS.items() if toks & words}


def attribution_speakers(sentence: str) -> set[str] | None:
    """None when the sentence has no attribution frame; else the stemmed
    content tokens (up to 3) immediately preceding the attribution verb."""
    toks = tokenize(sentence)
    speakers: set[str] = set()
    found = False
    for i, tok in enumerate(toks):
        if tok in _ATTRIBUTION_VERBS:
            found = True
            window = [t for t in toks[max(0, i - 3) : i] if t not in STOPWORDS and len(t) >= 2]
            speakers.update(light_stem(t) for t in window)
    return speakers if found else None


# ── the checks ────────────────────────────────────────────────────────────

def _compare_feature(
    alignments: list[Alignment],
    claim_feature,
    evidence_feature,
    disagrees,
    kind: str,
    describe,
) -> CheckResult:
    """Generic 'claim vs aligned evidence' comparison: a discrepancy is raised
    only when NO equally-aligned evidence sentence agrees and at least one
    disagrees."""
    evaluated = 0
    discs: list[Discrepancy] = []
    for al in alignments:
        if not al.aligned:
            continue
        cf = claim_feature(al.claim.text)
        if cf is None:
            continue
        evaluated += 1
        verdicts = []
        for es, _ in al.evidence:
            ef = evidence_feature(es.text)
            verdicts.append((es, disagrees(cf, ef)))
        if verdicts and all(v is True for _, v in verdicts):
            es = verdicts[0][0]
            discs.append(
                Discrepancy(kind, al.claim.text, es.text, describe(cf, evidence_feature(es.text)), al.claim.part)
            )
    if discs:
        return CheckResult(CheckState.FAILED, discs)
    if evaluated == 0:
        return CheckResult(CheckState.NOT_APPLICABLE, note="nothing to compare")
    return CheckResult(CheckState.PASSED)


def check_negation(alignments: list[Alignment]) -> CheckResult:
    if not any(a.aligned for a in alignments):
        return CheckResult(CheckState.NOT_EVALUATED, note="no aligned source sentence")
    res = _compare_feature(
        alignments,
        claim_feature=lambda s: is_negated(s),
        evidence_feature=lambda s: is_negated(s),
        disagrees=lambda c, e: c != e,
        kind="negation",
        describe=lambda c, e: (
            "the claim negates a statement the source affirms"
            if c
            else "the claim affirms a statement the source negates"
        ),
    )
    # Negation always has something to compare once aligned.
    if res.state == CheckState.NOT_APPLICABLE:
        return CheckResult(CheckState.PASSED)
    return res


def check_modality(alignments: list[Alignment]) -> CheckResult:
    if not any(a.aligned for a in alignments):
        return CheckResult(CheckState.NOT_EVALUATED, note="no aligned source sentence")
    return _compare_feature(
        alignments,
        claim_feature=lambda s: (m if (m := modality(s)) != "UNKNOWN" else None),
        evidence_feature=modality,
        disagrees=lambda c, e: e != "UNKNOWN" and e != c,
        kind="modality",
        describe=lambda c, e: (
            "the claim reports a completed event; the source describes a plan, "
            "possibility or future event"
            if c == "COMPLETED"
            else "the claim describes a plan or possibility; the source reports it as completed"
        ),
    )


def check_scope(alignments: list[Alignment]) -> CheckResult:
    if not any(a.aligned for a in alignments):
        return CheckResult(CheckState.NOT_EVALUATED, note="no aligned source sentence")

    def disagrees(c: set[str], e: set[str]) -> bool:
        for a, b in _CONFLICTS:
            for x, y in ((a, b), (b, a)):
                if x in c and y in e and x not in e:
                    return True
        return False

    return _compare_feature(
        alignments,
        claim_feature=lambda s: (g if (g := qualifier_groups(s)) else None),
        evidence_feature=qualifier_groups,
        disagrees=disagrees,
        kind="scope",
        describe=lambda c, e: (
            f"quantifier/scope differs (claim: {', '.join(sorted(c))}; "
            f"source: {', '.join(sorted(e)) or 'none'})"
        ),
    )


def check_attribution(alignments: list[Alignment]) -> CheckResult:
    if not any(a.aligned for a in alignments):
        return CheckResult(CheckState.NOT_EVALUATED, note="no aligned source sentence")
    claim_has = any(attribution_speakers(a.claim.text) is not None for a in alignments if a.aligned)
    if not claim_has:
        return CheckResult(CheckState.NOT_APPLICABLE, note="claim states no attribution")

    discs: list[Discrepancy] = []
    evaluated = 0
    for al in alignments:
        if not al.aligned:
            continue
        cs = attribution_speakers(al.claim.text)
        if cs is None:
            continue
        ev = [(es, attribution_speakers(es.text)) for es, _ in al.evidence]
        ev_frames = [(es, s) for es, s in ev if s]
        if not ev_frames:
            continue  # source has no attribution frame to compare — unsupported, not contradicted
        evaluated += 1
        if not any(cs & s for _, s in ev_frames):
            discs.append(
                Discrepancy(
                    "attribution",
                    al.claim.text,
                    ev_frames[0][0].text,
                    "the statement is attributed to a different speaker than in the source",
                    al.claim.part,
                )
            )
    if discs:
        return CheckResult(CheckState.FAILED, discs)
    if evaluated == 0:
        return CheckResult(CheckState.NOT_EVALUATED, note="source states no comparable attribution")
    return CheckResult(CheckState.PASSED)


def check_numbers(alignments: list[Alignment], all_evidence_text: str) -> CheckResult:
    claim_has = any(parse_number_phrases(a.claim.text) for a in alignments)
    if not claim_has:
        return CheckResult(CheckState.NOT_APPLICABLE, note="claim contains no numbers")
    if not any(a.aligned for a in alignments):
        return CheckResult(CheckState.NOT_EVALUATED, note="no aligned source sentence")

    anywhere = parse_number_phrases(all_evidence_text)
    discs: list[Discrepancy] = []
    unsupported: list[str] = []
    for al in alignments:
        cnums = parse_number_phrases(al.claim.text)
        if not cnums:
            continue
        if not al.aligned:
            unsupported.extend(s for _, _, s in cnums)
            continue
        ev_nums = [(es, parse_number_phrases(es.text)) for es, _ in al.evidence]
        for value, unit, surface in cnums:
            def same(ev_value: float, ev_unit: str | None) -> bool:
                return abs(ev_value - value) < 1e-9 and (unit is None or ev_unit is None or unit == ev_unit)

            if any(same(v, u) for _, nums in ev_nums for v, u, _s in nums):
                continue
            # comparable number in the aligned sentence with the same unit?
            comparable = None
            for es, nums in ev_nums:
                for v, u, s in nums:
                    if (unit is not None and u == unit) or (
                        unit is None and len(cnums) == 1 and len(nums) == 1
                    ):
                        comparable = (es, s)
                        break
                if comparable:
                    break
            if comparable:
                es, ev_surface = comparable
                discs.append(
                    Discrepancy(
                        "numbers",
                        al.claim.text,
                        es.text,
                        f"claimed {surface}, source states {ev_surface}",
                        al.claim.part,
                        {"claimed": surface, "source": ev_surface},
                    )
                )
            elif any(same(v, u) for v, u, _s in anywhere):
                continue  # the number is in the article, just not in the aligned sentence
            else:
                unsupported.append(surface)
    if discs:
        return CheckResult(CheckState.FAILED, discs)
    if unsupported:
        return CheckResult(
            CheckState.NOT_EVALUATED,
            note="claimed number(s) not found in the source and not contradicted: "
            + ", ".join(unsupported),
        )
    return CheckResult(CheckState.PASSED)


def check_entities(
    alignments: list[Alignment],
    claim_mentions: list[EntityMention],
    evidence_mentions: list[EntityMention],
    *,
    ner_available: bool,
) -> CheckResult:
    """Entity substitution and role swap — never inferred from low overlap."""
    if not ner_available:
        return CheckResult(CheckState.NOT_EVALUATED, note="NER unavailable")
    if not claim_mentions:
        return CheckResult(CheckState.NOT_APPLICABLE, note="claim names no entities")
    if not any(a.aligned for a in alignments):
        return CheckResult(CheckState.NOT_EVALUATED, note="no aligned source sentence")

    discs: list[Discrepancy] = []
    for al in alignments:
        if not al.aligned:
            continue
        es, _ = al.evidence[0]
        cm = mentions_in_sentence(al.claim.text, claim_mentions)
        em = mentions_in_sentence(es.text, evidence_mentions)
        if not cm:
            continue
        ev_tokens = tuple(light_stem(t) for t in tokenize(es.text))
        status = {m.text: match_entity(m, em, ev_tokens) for m in cm}
        claim_keys = {m.key for m in cm}

        # Substitution: unmatched claim entity <-> unclaimed evidence entity of
        # the SAME type AND the SAME grammatical role, unambiguously.
        for m in cm:
            if status[m.text].status != "unmatched":
                continue
            role = detect_role(al.claim.text, m.text)
            cands = [
                e
                for e in em
                if e.type == m.type
                and e.key not in claim_keys
                and detect_role(es.text, e.text) == role
                and role != "UNKNOWN"
            ]
            if len(cands) == 1:
                discs.append(
                    Discrepancy(
                        "entity_substitution",
                        al.claim.text,
                        es.text,
                        f"{m.type} '{m.text}' appears where the source names '{cands[0].text}' ({role.lower()})",
                        al.claim.part,
                        {"type": m.type, "claimed": m.text, "source": cands[0].text, "role": role},
                    )
                )

        # Role swap: two entities present in both sentences with exchanged roles.
        both = [m for m in cm if status[m.text].matched]
        for i in range(len(both)):
            for j in range(i + 1, len(both)):
                a, b = both[i], both[j]
                rca, rcb = detect_role(al.claim.text, a.text), detect_role(al.claim.text, b.text)
                rea, reb = detect_role(es.text, a.text), detect_role(es.text, b.text)
                known = {rca, rcb, rea, reb}
                if "UNKNOWN" in known:
                    continue
                if rca != rcb and rca == reb and rcb == rea:
                    discs.append(
                        Discrepancy(
                            "entity_role",
                            al.claim.text,
                            es.text,
                            f"'{a.text}' and '{b.text}' have exchanged roles relative to the source",
                            al.claim.part,
                        )
                    )
    if discs:
        return CheckResult(CheckState.FAILED, discs)
    return CheckResult(CheckState.PASSED)


def run_checks(
    claim_sentences: list[ClaimSentence],
    evidence_sentences: list[EvidenceSentence],
    claim_mentions: list[EntityMention],
    evidence_mentions: list[EntityMention],
    *,
    ner_available: bool,
) -> dict[str, CheckResult]:
    return analyze(
        claim_sentences,
        evidence_sentences,
        claim_mentions,
        evidence_mentions,
        ner_available=ner_available,
    )[0]


def analyze(
    claim_sentences: list[ClaimSentence],
    evidence_sentences: list[EvidenceSentence],
    claim_mentions: list[EntityMention],
    evidence_mentions: list[EntityMention],
    *,
    ner_available: bool,
) -> tuple[dict[str, CheckResult], list[Alignment]]:
    """All six checks plus the sentence alignments they were computed from
    (callers derive per-part headline/body states from the alignments)."""
    alignments = align_sentences(claim_sentences, evidence_sentences)
    all_text = " ".join(es.text for es in evidence_sentences)
    results = {
        "numbers": check_numbers(alignments, all_text),
        "negation": check_negation(alignments),
        "entities": check_entities(
            alignments, claim_mentions, evidence_mentions, ner_available=ner_available
        ),
        "scope": check_scope(alignments),
        "attribution": check_attribution(alignments),
        "modality": check_modality(alignments),
    }
    return results, alignments


def sentences_of(text: str, part: str) -> list[ClaimSentence]:
    return [ClaimSentence(s, part) for s in split_sentences(text, min_len=4)]
