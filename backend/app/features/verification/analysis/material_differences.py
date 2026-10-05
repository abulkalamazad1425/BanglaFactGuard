"""Deterministic, quotable differences between a claim headline and a source title.

Every rule here looks for ONE concrete kind of meaning change and, when it
fires, returns the claim text and source text that show it. A rule never
fires on a mere absence of overlap: "these share few words" is not a
material difference, it is something the semantic assessment in
`headline_comparison.py` has to judge.

Rules (all applied to the headline and the title only — never a body):

  numbers         a claimed number/quantity the title does not state, or a
                  different value for the same referent (৫ জন -> ১০ জন)
  date            a claimed date word (month, weekday, আজ/গতকাল...) the
                  title does not carry, or a different one
  negation        the claim negates what the title affirms, or the reverse
  modality        completed event vs plan/possibility/future
  scope           a conflicting quantifier (সব vs কিছু, অন্তত vs সর্বোচ্চ)
  subject_object  who did what to whom is reversed
  attribution     the title reports an allegation/claim; the headline
                  states it as fact
  denial          the title disputes/denies; the headline does not
  entity          the headline names a person/place/organisation the title
                  does not (only when NER is usable)

All text is compared through the same Bangla normalisation and light
stemming (`analysis/text.py`) on both sides.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.features.verification.analysis.entities import EntityMention, match_entity, mentions_in_sentence
from app.features.verification.analysis.keywords import _evidence_keys, extract_claim_units
from app.features.verification.analysis.text import (
    QUALIFIER_GROUPS,
    QUALIFIER_WORDS,
    STOPWORDS,
    light_stem,
    normalize_for_match,
    tokenize,
)


@dataclass(frozen=True)
class MaterialDifference:
    kind: str
    detail: str
    claim_text: str
    source_text: str
    meta: dict[str, str] = field(default_factory=dict)


def _n(text: str) -> str:
    return normalize_for_match(text)


def _norm_words(*words: str) -> frozenset[str]:
    """Word lists in exactly the form `tokenize` produces for compared text."""
    return frozenset(t for w in words for t in tokenize(w))


def _any_of(*words: str) -> str:
    return "(?:" + "|".join(re.escape(_n(w)) for w in words) + ")"


# ── content words ────────────────────────────────────────────────────────

def content_units(text: str):
    return [u for u in extract_claim_units(text) if u.kind == "content"]


def coverage(units, keys: set[str]) -> float:
    if not units:
        return 0.0
    return sum(1 for u in units if {u.text, light_stem(u.text)} & keys) / len(units)


def unmatched_content(claim: str, source: str) -> list[str]:
    """Claim content words (stem-aware) that do not occur in the source."""
    keys = _evidence_keys(source)
    return [u.text for u in extract_claim_units(claim) if not ({u.text, light_stem(u.text)} & keys)]


def same_word_sequence(a: str, b: str) -> bool:
    """Same words in the same order — only punctuation/spacing differs."""
    ta, tb = tokenize(a), tokenize(b)
    return bool(ta) and ta == tb


# ── negation, modality, scope, attribution ───────────────────────────────

_NEGATION_WORDS = _norm_words("না", "নি", "নেই", "নয়", "নয়", "নন", "নাই", "নাকচ", "not", "no", "never")
# Fused verb negation (হয়নি, করেনি, দেননি, যায়নি). The letter before নি must
# be এ-কার, য় or ন, so nouns such as পানি, জানি, কোম্পানি do not match.
_FUSED_NEGATION_RE = re.compile(
    "^.+(?:" + "|".join(re.escape(_n(s)) for s in ("ে", "য়", "য়", "ন")) + ")" + re.escape(_n("নি")) + "$"
)
_PLAN_WORDS = _norm_words(
    "পারে", "পারেন", "সম্ভাবনা", "আশঙ্কা", "পরিকল্পনা", "পরিকল্পনায়", "প্রস্তাব",
    "প্রস্তাবিত", "উদ্যোগ", "সম্ভবত", "নাকি", "বিবেচনা", "চিন্তা", "ভাবছে", "ভাবছেন",
    "চায়", "চান", "সম্ভাব্য", "প্রস্তুতি", "যাচ্ছে", "যাচ্ছেন",
)
_COMPLETED_WORDS = _norm_words("হলো", "হল", "করল", "দিল", "গেল", "ঘটল", "বলল", "হয়েছিল", "মারা", "পাস")
_COMPLETED_ENDINGS = tuple(_n(s) for s in ("েছে", "েছেন", "েছিল", "েছিলেন", "েছিলো", "লেন"))
_FUTURE_ENDINGS = tuple(_n(s) for s in ("বে", "বেন", "বো"))
# Words ending like a future verb that are not one: ভালোভাবে, জবাবে, হিসেবে, তবে.
_NOT_FUTURE_ENDINGS = tuple(_n(s) for s in ("ভাবে", "জবাবে", "হিসেবে", "হিসাবে"))
_NOT_FUTURE_WORDS = _norm_words("তবে", "কবে", "সবে", "যবে")
_DENIAL_WORDS = _norm_words("গুজব", "মিথ্যা", "ভুয়া", "অসত্য", "বানোয়াট", "ভিত্তিহীন")
_DENIAL_RE = re.compile(_any_of("সত্য", "সঠিক") + r"\s+" + _any_of("নয়", "নয়", "না"))
# An allegation/claim FRAME ("অভিযোগ করেছে", "বলে দাবি", "অভিযোগ:"), not the
# bare noun - দাবি alone also means "demand" (শিক্ষার্থীদের দাবি মেনে নিল সরকার).
_ALLEGATION_SOURCE_RE = re.compile(
    _any_of("দাবি", "অভিযোগ") + r"\s+" + _any_of("কর", "তোল", "তুল", "জানা", "উঠেছে", "ওঠে")
    + "|" + _any_of("বলে") + r"\s+" + _any_of("দাবি", "অভিযোগ")
    + "|" + _any_of("দাবি", "অভিযোগ") + r"\s*[:：]"
)
_ALLEGATION_CLAIM_RE = re.compile(_any_of("দাবি", "অভিযোগ", "গুজব"))
_CONFLICTING_SCOPES = (("UNIVERSAL", "PARTIAL"), ("LOWER_BOUND", "UPPER_BOUND"))

_CLAUSE_SPLIT_RE = re.compile(
    r"\s*(?:,(?![0-9০-৯])|:(?![0-9০-৯])|[;—–])\s*|\s+-\s+|\s+(?:কিন্তু|তবে|অথচ|যদিও|এবং)\s+"
)
CLAUSE_ALIGN = 0.6


def _is_negation(tok: str, prev: str = "") -> bool:
    if tok in _NEGATION_WORDS:
        return not (tok == _n("না") and prev == _n("কি"))  # কি না = "whether"
    return len(tok) >= 4 and bool(_FUSED_NEGATION_RE.match(tok))


def polarity(text: str) -> bool:
    """True when the text is negated (an odd number of negations)."""
    toks = tokenize(text)
    return sum(_is_negation(t, toks[i - 1] if i else "") for i, t in enumerate(toks)) % 2 == 1


def _same_predicate(a: str, b: str) -> bool:
    """A fused negation hides its verb (কমায়নি). Only compare polarity when
    the other side uses the same verb root (কমিয়েছে), so 'did not raise' is
    never read as the negation of 'reduced'."""
    for x, y in ((a, b), (b, a)):
        other = tokenize(y)
        for tok in tokenize(x):
            if tok not in _NEGATION_WORDS and _is_negation(tok):
                root = tok[:-2][:2]
                if not any(t.startswith(root) and t != tok for t in other):
                    return False
    return True


def _is_future(tok: str) -> bool:
    return (
        len(tok) >= 3
        and tok.endswith(_FUTURE_ENDINGS)
        and tok not in _NOT_FUTURE_WORDS
        and not tok.endswith(_NOT_FUTURE_ENDINGS)
    )


def modality(text: str) -> str:
    """COMPLETED | NOT_COMPLETED (planned, possible, future) | UNKNOWN."""
    toks = tokenize(text)
    if any(t in _PLAN_WORDS or _is_future(t) for t in toks):
        return "NOT_COMPLETED"
    if any(t in _COMPLETED_WORDS or (len(t) >= 4 and t.endswith(_COMPLETED_ENDINGS)) for t in toks):
        return "COMPLETED"
    return "UNKNOWN"


def qualifier_groups(text: str) -> set[str]:
    toks = set(tokenize(text))
    return {g for g, words in QUALIFIER_GROUPS.items() if toks & words}


def _scope_conflict(a: str, b: str) -> bool:
    ga, gb = qualifier_groups(a), qualifier_groups(b)
    return any(
        x in ga and y in gb and x not in gb
        for p, q in _CONFLICTING_SCOPES
        for x, y in ((p, q), (q, p))
    )


def _clauses(text: str) -> list[str]:
    return [c.strip() for c in _CLAUSE_SPLIT_RE.split(text) if c and c.strip()] or [text]


def _clause_alignment(claim: str, source: str):
    """Pair each claim clause with the source clause that discusses it:
    (claim_clause, source_clause, ambiguous). `ambiguous` when equally
    aligned source clauses disagree in polarity or modality."""
    src = _clauses(source)
    src_keys = [_evidence_keys(s) for s in src]
    aligned = []
    for cc in _clauses(claim):
        units = content_units(cc)
        if len(units) < 2:
            continue
        scores = [coverage(units, k) for k in src_keys]
        best = max(scores)
        if best < CLAUSE_ALIGN:
            continue
        tops = [src[i] for i, s in enumerate(scores) if s >= best - 1e-9]
        ambiguous = len({polarity(t) for t in tops}) > 1 or len({modality(t) for t in tops}) > 1
        aligned.append((cc, tops[0], ambiguous))
    return aligned


# ── subject / object roles ───────────────────────────────────────────────
# Object-case endings (X-কে, X-দের/-দেরকে as accusative) versus a bare
# or nominative-plural (X-রা, X-গণ) form of the same word. A role swap needs
# a flip in BOTH directions, so a single genitive "-দের" cannot fire it.
_OBJECT_ENDINGS = tuple(_n(s) for s in ("দেরকে", "কে", "দের"))
_SUBJECT_ENDINGS = tuple(_n(s) for s in ("েরা", "রা", "গণ"))


def _roles(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for tok in tokenize(text):
        if tok in STOPWORDS or len(tok) < 3:
            continue
        role, stem = "subject", tok
        for end in _OBJECT_ENDINGS:
            if tok.endswith(end) and len(tok) - len(end) >= 2:
                role, stem = "object", tok[: -len(end)]
                break
        else:
            for end in _SUBJECT_ENDINGS:
                if tok.endswith(end) and len(tok) - len(end) >= 2:
                    stem = tok[: -len(end)]
                    break
        out.setdefault(light_stem(stem), role)
    return out


def role_swap(claim: str, source: str) -> tuple[str, str] | None:
    """(word that became the object, word that became the subject) when the
    headline reverses who did what to whom relative to the title."""
    rc, rs = _roles(claim), _roles(source)
    to_object = [k for k in rc if k in rs and rc[k] == "object" and rs[k] == "subject"]
    to_subject = [k for k in rc if k in rs and rc[k] == "subject" and rs[k] == "object"]
    if to_object and to_subject:
        return to_object[0], to_subject[0]
    return None


# ── numbers and dates ────────────────────────────────────────────────────

_MAGNITUDES = {_n("শত"): 100, _n("হাজার"): 1_000, _n("লাখ"): 100_000, _n("লক্ষ"): 100_000, _n("কোটি"): 10_000_000}
_NUMBER_WORDS = {
    _n(w): v
    for w, v in {
        "দুই": 2, "তিন": 3, "চার": 4, "পাঁচ": 5, "ছয়": 6, "সাত": 7, "আট": 8, "দশ": 10,
        "বিশ": 20, "ত্রিশ": 30, "চল্লিশ": 40, "পঞ্চাশ": 50,
    }.items()
}
_UNITS = tuple(
    _n(u)
    for u in (
        "কিলোমিটার", "মেগাওয়াট", "শতাংশ", "টাকা", "ডলার", "রুপি", "ইউরো", "কেজি", "টন",
        "লিটার", "একর", "মিটার", "জন", "বছর", "মাস", "দিন", "ঘণ্টা", "মিনিট", "টি", "বার",
    )
) + ("%",)
_CURRENCIES = frozenset(_n(u) for u in ("টাকা", "ডলার", "রুপি", "ইউরো"))
_ROLES = tuple(
    _n(r)
    for r in (
        "নিহত", "মৃত্যু", "মারা", "আহত", "নিখোঁজ", "আক্রান্ত", "গ্রেপ্তার", "আটক", "উদ্ধার",
        "বরাদ্দ", "ব্যয়", "খরচ", "ঋণ", "জরিমানা", "আয়", "বেতন", "শুল্ক", "দাম", "মূল্য",
        "ভাড়া", "বাজেট", "রপ্তানি", "আমদানি", "প্রবৃদ্ধি", "মূল্যস্ফীতি", "ভোট", "আসন",
    )
)
_QUANTITY_RE = re.compile(
    r"(?<![0-9.,])([0-9]+(?:,[0-9]+)*(?:\.[0-9]+)?)\s*"
    r"((?:" + "|".join(map(re.escape, _MAGNITUDES)) + r")(?![ঀ-৿]))?\s*"
    r"(" + "|".join(map(re.escape, _UNITS)) + r")?"
)
_PERCENT = _n("শতাংশ")
_TO_BANGLA_DIGITS = str.maketrans("0123456789", "০১২৩৪৫৬৭৮৯")


@dataclass(frozen=True)
class Quantity:
    value: float
    unit: str
    role: str
    surface: str


def _role_in(tokens: list[str]) -> list[str]:
    return [r for r in _ROLES if any(t == r or light_stem(t) == r for t in tokens)]


def quantities(text: str) -> list[Quantity]:
    """Numbers with unit and (when clear) referent: ৫ জন নিহত, ২০ শতাংশ."""
    norm = _n(text)
    for word, value in _NUMBER_WORDS.items():
        norm = re.sub(r"(?<!\S)" + re.escape(word) + r"(?=\s)", str(value), norm)
    hits = [m for m in _QUANTITY_RE.finditer(norm) if m.group(1)]
    out: list[Quantity] = []
    for i, m in enumerate(hits):
        left = norm[hits[i - 1].end() if i else 0 : m.start()]
        right = norm[m.end() : hits[i + 1].start() if i + 1 < len(hits) else len(norm)]
        roles = _role_in(tokenize(right)[:4]) or _role_in(tokenize(left)[-4:])
        unit = _PERCENT if m.group(3) == "%" else (m.group(3) or "")
        try:
            value = float(m.group(1).replace(",", "")) * _MAGNITUDES.get(m.group(2) or "", 1)
        except ValueError:
            continue
        out.append(Quantity(value, unit, roles[0] if len(roles) == 1 else "", m.group(0).strip()))
    return out


def _same_value(a: Quantity, b: Quantity) -> bool:
    return abs(a.value - b.value) <= 1e-9 * max(1.0, abs(a.value))


def _compatible(a: Quantity, b: Quantity) -> bool:
    return (not a.role or not b.role or a.role == b.role) and (
        not a.unit or not b.unit or a.unit == b.unit or {a.unit, b.unit} <= _CURRENCIES
    )


def _bangla_digits(text: str) -> str:
    return text.translate(_TO_BANGLA_DIGITS)


_DATE_WORDS = {
    light_stem(t): canonical
    for canonical, forms in {
        "জানুয়ারি": ("জানুয়ারি", "জানুয়ারি", "january"),
        "ফেব্রুয়ারি": ("ফেব্রুয়ারি", "ফেব্রুয়ারি", "february"),
        "মার্চ": ("মার্চ", "march"),
        "এপ্রিল": ("এপ্রিল", "april"),
        "মে": ("may",),
        "জুন": ("জুন", "june"),
        "জুলাই": ("জুলাই", "july"),
        "আগস্ট": ("আগস্ট", "আগষ্ট", "august"),
        "সেপ্টেম্বর": ("সেপ্টেম্বর", "september"),
        "অক্টোবর": ("অক্টোবর", "october"),
        "নভেম্বর": ("নভেম্বর", "november"),
        "ডিসেম্বর": ("ডিসেম্বর", "december"),
        "শনিবার": ("শনিবার",), "রবিবার": ("রবিবার", "রোববার"), "সোমবার": ("সোমবার",),
        "মঙ্গলবার": ("মঙ্গলবার",), "বুধবার": ("বুধবার",), "বৃহস্পতিবার": ("বৃহস্পতিবার",),
        "শুক্রবার": ("শুক্রবার",),
        "আজ": ("আজ", "আজকে"), "গতকাল": ("গতকাল",), "আগামীকাল": ("আগামীকাল",),
    }.items()
    for f in forms
    for t in tokenize(f)
}


def date_words(text: str) -> set[str]:
    return {_DATE_WORDS[light_stem(t)] for t in tokenize(text) if light_stem(t) in _DATE_WORDS}


# ── the rules ────────────────────────────────────────────────────────────

def find_material_differences(
    claim: str,
    source: str,
    *,
    claim_mentions: list[EntityMention] | None = None,
    source_mentions: list[EntityMention] | None = None,
    ner_available: bool = False,
) -> list[MaterialDifference]:
    """Every concrete meaning change between `claim` and `source`."""
    found: list[MaterialDifference] = []

    def add(kind: str, detail: str, claim_text: str = claim, source_text: str = source, **meta: str) -> None:
        found.append(MaterialDifference(kind, detail, claim_text, source_text, dict(meta)))

    # numbers
    sq = quantities(source)
    for q in quantities(claim):
        if any(_same_value(q, e) and _compatible(q, e) for e in sq):
            continue
        rivals = [e for e in sq if _compatible(q, e) and (q.role and e.role == q.role or q.unit and e.unit == q.unit)]
        claimed = _bangla_digits(q.surface)
        if len(rivals) == 1:
            stated = _bangla_digits(rivals[0].surface)
            what = f"{q.role}: " if q.role else ""
            add("numbers", f"{what}the headline states {claimed}; the source title states {stated}.",
                claim_text=claimed, source_text=stated)
        else:
            add("numbers", f"The headline states {claimed}, which the source title does not state.",
                claim_text=claimed)

    # dates
    cd, sd = date_words(claim), date_words(source)
    extra = cd - sd
    if extra:
        if sd - cd:
            add("date", f"The headline's date ({', '.join(sorted(extra))}) differs from the source title's "
                f"({', '.join(sorted(sd - cd))}).", claim_text=", ".join(sorted(extra)),
                source_text=", ".join(sorted(sd - cd)))
        else:
            add("date", f"The headline adds a date ({', '.join(sorted(extra))}) the source title does not state.",
                claim_text=", ".join(sorted(extra)))

    # negation / modality / scope on aligned clauses
    for cc, sc, ambiguous in _clause_alignment(claim, source):
        if ambiguous:
            continue
        if polarity(cc) != polarity(sc) and _same_predicate(cc, sc):
            add("negation", "The headline negates what the source title affirms." if polarity(cc)
                else "The headline affirms what the source title negates.", claim_text=cc, source_text=sc)
        elif {modality(cc), modality(sc)} == {"COMPLETED", "NOT_COMPLETED"}:
            add("modality", "The headline reports a completed event; the source title describes a plan, "
                "possibility or future event." if modality(cc) == "COMPLETED"
                else "The headline describes a plan or possibility; the source title reports it as completed.",
                claim_text=cc, source_text=sc)
        elif _scope_conflict(cc, sc):
            add("scope", f"The quantifier differs (headline: {', '.join(sorted(qualifier_groups(cc)))}; "
                f"source title: {', '.join(sorted(qualifier_groups(sc)))}).", claim_text=cc, source_text=sc)

    # subject / object
    swap = role_swap(claim, source)
    if swap:
        add("subject_object", f"Who did what to whom is reversed: '{swap[0]}' and '{swap[1]}' exchange roles "
            "relative to the source title.", a=swap[0], b=swap[1])

    # attribution / denial
    if _ALLEGATION_SOURCE_RE.search(_n(source)) and not _ALLEGATION_CLAIM_RE.search(_n(claim)):
        add("attribution", "The source title reports this as someone's claim or allegation; the headline "
            "states it as established fact.")
    if (set(tokenize(source)) & _DENIAL_WORDS or _DENIAL_RE.search(_n(source))) and not (
        set(tokenize(claim)) & _DENIAL_WORDS or _DENIAL_RE.search(_n(claim))
    ):
        add("denial", "The source title disputes or denies this; the headline does not.")

    # named entities
    if ner_available and claim_mentions:
        src_mentions = source_mentions or []
        src_keys = tuple(light_stem(t) for t in tokenize(source))
        for m in mentions_in_sentence(claim, claim_mentions):
            if match_entity(m, src_mentions, src_keys).matched:
                continue
            rivals = [s.text for s in src_mentions if s.type == m.type
                      and not match_entity(s, claim_mentions, tuple(light_stem(t) for t in tokenize(claim))).matched]
            if rivals:
                add("entity", f"The headline names {m.text}; the source title names {', '.join(rivals)} instead.",
                    claim_text=m.text, source_text=", ".join(rivals), type=m.type)
            else:
                add("entity", f"The headline names {m.text}, who/which the source title does not mention.",
                    claim_text=m.text, type=m.type)

    return found


__all__ = [
    "MaterialDifference",
    "QUALIFIER_WORDS",
    "content_units",
    "coverage",
    "date_words",
    "find_material_differences",
    "modality",
    "polarity",
    "quantities",
    "qualifier_groups",
    "role_swap",
    "same_word_sequence",
    "unmatched_content",
]
