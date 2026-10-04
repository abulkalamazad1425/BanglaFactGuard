"""Claim ↔ source content comparison, statement by statement, locally.

Answers one question: does the submitted claim carry the same material facts
as the source report? Whether the report itself is true is out of scope.

The same code checks a photo-card headline, a headline-only text claim and a
headline + body text claim. No third-party inference API is called: the
already-loaded local embedding / NLI / NER services and deterministic rules
do all the work.

Each submitted statement (headline sentence, or material body sentence) is
compared with the source title and the source body sentences:

1. Evidence selection. Source sentences are ranked by how many of the
   statement's content words they contain and by local embedding similarity.
   This only chooses what to compare against; a score never decides.
2. Verbatim. The statement is the source's own text (or a contiguous excerpt
   that drops nothing meaning-bearing): SUPPORTED.
3. Concrete conflict with a well-aligned source sentence: changed number for
   the same referent, flipped negation, plan <-> completed event, changed
   quantifier/bound, entity substitution or role swap, an allegation
   presented as fact: CONTRADICTED, with both texts quoted.
4. Facts preserved. Every content word, number and named entity of the
   statement is in the source passage, and negation, tense and quantifiers
   agree: SUPPORTED. Shortening and reordering are fine.
5. Paraphrase. The local NLI model entails the statement from the passage and
   the statement's numbers and names are present: SUPPORTED.
6. Otherwise INSUFFICIENT_EVIDENCE, with the specific reason.

`decisions.decide_content` turns the findings into MATCHED / ALTERED /
INCOMPLETE. The publication date takes no part.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import numpy as np
import structlog

from app.core.config import get_settings
from app.core.constants import CheckState, ManipulationType
from app.features.verification.analysis.discrepancies import (
    Alignment,
    ClaimSentence,
    EvidenceSentence,
    check_entities,
    qualifier_groups,
)
from app.features.verification.analysis.entities import (
    EntityMention,
    match_entity,
    mentions_in_sentence,
)
from app.features.verification.analysis.keywords import _evidence_keys, extract_claim_units
from app.features.verification.analysis.text import (
    QUALIFIER_WORDS,
    STOPWORDS,
    light_stem,
    normalize_for_match,
    tokenize,
)
from app.features.verification.schemas import (
    AlteredNumberDetail,
    ContentCheck,
    ContentEvidence,
    ContentFinding,
    DiscrepancyDetail,
    ManipulationFlagsSchema,
    SubstitutedEntityDetail,
)

logger = structlog.get_logger(__name__)

METHOD = "local-claim-evidence-v3"

SUPPORTED = "SUPPORTED"
CONTRADICTED = "CONTRADICTED"
INSUFFICIENT = "INSUFFICIENT_EVIDENCE"

ALIGN_CANDIDATE = 0.5        # content-word coverage that makes a sentence a candidate
SEM_CANDIDATE = 0.6          # ...or local embedding similarity (selection only)
ALIGN_CONFLICT = 0.7         # a concrete conflict needs this much shared content
CLAUSE_ALIGN = 0.6
TIE_BAND = 0.1
MAX_CANDIDATES = 4
MAX_STATEMENTS = 150
MAX_SOURCE_SENTENCES = 800
MAX_NLI_CALLS = 240
NLI_HYPOTHESIS_CHARS = 300   # NLIService truncates beyond these; never feed it more
NLI_PREMISE_CHARS = 1200
ENTAILMENT_MIN = 0.80
STRONG_ENTAILMENT = 0.90
NLI_SUPPORT_MAX_CONTRADICTION = 0.20
VALIDATED_CONTRADICTION_MIN = 0.90
NER_BATCH_CHARS = 12_000     # under NERService's 40 x 350-char chunk cap


def _norm_words(*words: str) -> frozenset[str]:
    """Word lists in exactly the form `tokenize` produces for compared text."""
    return frozenset(t for w in words for t in tokenize(w))


def _n(text: str) -> str:
    return normalize_for_match(text)


# ── sentences, clauses, keywords ─────────────────────────────────────────

_SENTENCE_RE = re.compile(r"[^\n]+?(?:[।!?‼]+|\.(?=\s)|(?=\n)|$)")
_CLAUSE_SPLIT_RE = re.compile(
    r"\s*(?:,(?![0-9০-৯])|:(?![0-9০-৯])|[;—–])\s*|\s+-\s+|\s+(?:কিন্তু|তবে|অথচ|যদিও|এবং)\s+"
)
_BOILERPLATE_RE = re.compile(
    r"^(?:আরও পড়ুন|আরো পড়ুন|ছবি\s*:|ফাইল ছবি|প্রতীকী ছবি|বিজ্ঞাপন|সূত্র\s*:|"
    r"নিজস্ব প্রতিবেদক|প্রকাশ\s*:|আপডেট\s*:|হালনাগাদ\s*:|read more|advertisement)",
    re.IGNORECASE,
)


def split_statements(text: str | None) -> list[tuple[int, int, str]]:
    """Verbatim (start, end, sentence) spans. A short token before a full stop
    (ড., মো., Mr.) is an abbreviation, not a sentence end."""
    spans: list[tuple[int, int, str]] = []
    text = text or ""
    for m in _SENTENCE_RE.finditer(text):
        sentence = m.group().strip()
        if not sentence:
            continue
        if spans and spans[-1][2].endswith(".") and _is_abbreviation(spans[-1][2]):
            start = spans[-1][0]
            spans[-1] = (start, m.end(), text[start : m.end()].strip())
        else:
            spans.append((m.start(), m.end(), sentence))
    return spans


def _is_abbreviation(sentence: str) -> bool:
    words = sentence[:-1].split()
    return bool(words) and 0 < len(words[-1]) <= 3 and not words[-1][-1].isdigit()


def _clauses(text: str) -> list[str]:
    return [c.strip() for c in _CLAUSE_SPLIT_RE.split(text) if c and c.strip()] or [text]


def _content_units(text: str):
    return [u for u in extract_claim_units(text) if u.kind == "content"]


def _coverage(units, keys: set[str]) -> float:
    if not units:
        return 0.0
    return sum(1 for u in units if {u.text, light_stem(u.text)} & keys) / len(units)


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
_ATTRIBUTION_WORDS = _norm_words(
    "বলেছেন", "বলেছে", "বলেন", "বলল", "বললেন", "বলছেন", "জানিয়েছেন", "জানিয়েছে",
    "জানান", "জানায়", "দাবি", "অভিযোগ", "ঘোষণা",
)
_DENIAL_WORDS = _norm_words("গুজব", "মিথ্যা", "ভুয়া", "অসত্য", "বানোয়াট", "ভিত্তিহীন")


def _any_of(*words: str) -> str:
    return "(?:" + "|".join(re.escape(_n(w)) for w in words) + ")"


_DENIAL_RE = re.compile(_any_of("সত্য", "সঠিক") + r"\s+" + _any_of("নয়", "নয়", "না"))
_ALLEGATION_SOURCE_RE = re.compile(_any_of("দাবি", "অভিযোগ") + r"\s+" + _any_of("কর", "তোল", "তুল"))
_ALLEGATION_CLAIM_RE = re.compile(_any_of("দাবি", "অভিযোগ", "গুজব"))
# "ঢাকা, ৩ অক্টোবর" - a dateline, not a statement.
_DATELINE_RE = re.compile(
    r"^[^\s,]+(?:\s[^\s,]+)?,\s*[0-9]{1,2}\s+"
    + _any_of(
        "জানুয়ারি", "ফেব্রুয়ারি", "মার্চ", "এপ্রিল", "মে", "জুন", "জুলাই", "আগস্ট",
        "সেপ্টেম্বর", "অক্টোবর", "নভেম্বর", "ডিসেম্বর",
    )
    + r"(?:\s+[0-9]{4})?\W*$"
)
_OBJECT_MARKER = _n("কে")
_CONFLICTING_SCOPES = (("UNIVERSAL", "PARTIAL"), ("LOWER_BOUND", "UPPER_BOUND"))


def _is_negation(tok: str, prev: str = "") -> bool:
    if tok in _NEGATION_WORDS:
        return not (tok == _n("না") and prev == _n("কি"))  # কি না = "whether"
    return len(tok) >= 4 and bool(_FUSED_NEGATION_RE.match(tok))


def _polarity(text: str) -> bool:
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


def _modality(text: str) -> str:
    """COMPLETED | NOT_COMPLETED (planned, possible, future) | UNKNOWN."""
    toks = tokenize(text)
    if any(t in _PLAN_WORDS or _is_future(t) for t in toks):
        return "NOT_COMPLETED"
    if any(t in _COMPLETED_WORDS or (len(t) >= 4 and t.endswith(_COMPLETED_ENDINGS)) for t in toks):
        return "COMPLETED"
    return "UNKNOWN"


def _modality_conflict(a: str, b: str) -> bool:
    return {_modality(a), _modality(b)} == {"COMPLETED", "NOT_COMPLETED"}


def _scope_conflict(a: str, b: str) -> bool:
    ga, gb = qualifier_groups(a), qualifier_groups(b)
    return any(
        x in ga and y in gb and x not in gb
        for p, q in _CONFLICTING_SCOPES
        for x, y in ((p, q), (q, p))
    )


def _denies(text: str) -> bool:
    return bool(set(tokenize(text)) & _DENIAL_WORDS) or bool(_DENIAL_RE.search(_n(text)))


def _drops_allegation(claim: str, source: str) -> bool:
    return bool(_ALLEGATION_SOURCE_RE.search(_n(source))) and not _ALLEGATION_CLAIM_RE.search(_n(claim))


def _role_flip(claim: str, source: str) -> bool:
    """X-কে in the claim where the source has bare X, and the reverse for
    another word: who did what to whom was exchanged."""
    def marked(toks):
        return {t[: -len(_OBJECT_MARKER)] for t in toks if len(t) > 3 and t.endswith(_OBJECT_MARKER)}

    ct, st = tokenize(claim), tokenize(source)
    cm, sm = marked(ct), marked(st)
    return bool((cm & set(st)) and (sm & set(ct)))


def _meaning_bearing(tok: str) -> bool:
    return (
        _is_negation(tok)
        or tok in _PLAN_WORDS
        or _is_future(tok)
        or tok in QUALIFIER_WORDS
        or tok in _DENIAL_WORDS
        or tok in _norm_words("দাবি", "অভিযোগ")
    )


def _verbatim(claim_toks: list[str], source_toks: list[str]) -> bool:
    """Identical, or a contiguous excerpt whose dropped text changes nothing
    (no negation, plan/future, quantifier, denial or allegation is lost)."""
    if not claim_toks:
        return False
    if claim_toks == source_toks:
        return True
    n = len(claim_toks)
    if n < 3:
        return False
    for i in range(len(source_toks) - n + 1):
        if source_toks[i : i + n] == claim_toks:
            return not any(_meaning_bearing(t) for t in source_toks[:i] + source_toks[i + n :])
    return False


def _clause_alignment(claim: str, evidence: str):
    """Pair each claim clause with the evidence clause that discusses it.

    Returns (aligned, unaligned): aligned items are (claim_clause,
    evidence_clause, coverage, ambiguous); `ambiguous` when equally aligned
    evidence clauses disagree in polarity or modality."""
    ev = _clauses(evidence)
    ev_keys = [_evidence_keys(e) for e in ev]
    aligned, unaligned = [], []
    for cc in _clauses(claim):
        units = _content_units(cc)
        if not units:
            continue
        scores = [_coverage(units, k) for k in ev_keys]
        best = max(scores)
        if best < CLAUSE_ALIGN:
            unaligned.append(cc)
            continue
        tops = [ev[i] for i, s in enumerate(scores) if s >= best - 1e-9]
        ambiguous = len({_polarity(t) for t in tops}) > 1 or len({_modality(t) for t in tops}) > 1
        aligned.append((cc, tops[0], best, ambiguous))
    return aligned, unaligned


# ── quantities bound to their referent ───────────────────────────────────

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
_TIME_UNITS = frozenset(_n(u) for u in ("বছর", "মাস", "দিন", "ঘণ্টা", "মিনিট"))
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


@dataclass(frozen=True)
class Quantity:
    value: float
    unit: str
    role: str      # a known referent (নিহত, বরাদ্দ ...)
    surface: str
    noun: str = ""  # else the noun right after the number; used only to pair conflicts


def _role_in(tokens: list[str]) -> list[str]:
    return [r for r in _ROLES if any(t == r or light_stem(t) == r for t in tokens)]


def _noun_after(tokens: list[str]) -> list[str]:
    """The word right after a number (৫০ হাজার কৃষক -> কৃষক) when no known
    referent is near; verbs, negations and function words are not referents."""
    if not tokens:
        return []
    tok = tokens[0]
    if (
        len(tok) < 2 or tok in STOPWORDS or tok[0].isdigit() or _is_negation(tok) or _is_future(tok)
        or tok in _COMPLETED_WORDS or tok.endswith(_COMPLETED_ENDINGS)
    ):
        return []
    return [light_stem(tok)]


def quantities(text: str) -> list[Quantity]:
    """Numbers with unit and referent (৫ জন নিহত, ২০ জন আহত, ৫০ হাজার কৃষক).
    A referent is a known role word right after the number, else right
    before it, else the noun right after it; an unclear referent stays empty
    and the number is then only compared through a unique shared unit."""
    norm = _n(text)
    for word, value in _NUMBER_WORDS.items():
        norm = re.sub(r"(?<!\S)" + re.escape(word) + r"(?=\s)", str(value), norm)
    hits = [m for m in _QUANTITY_RE.finditer(norm) if m.group(1)]
    out: list[Quantity] = []
    for i, m in enumerate(hits):
        left = norm[hits[i - 1].end() if i else 0 : m.start()]
        right = norm[m.end() : hits[i + 1].start() if i + 1 < len(hits) else len(norm)]
        roles = _role_in(tokenize(right)[:4]) or _role_in(tokenize(left)[-4:])
        nouns = [] if roles else _noun_after(tokenize(right))
        unit = _PERCENT if m.group(3) == "%" else (m.group(3) or "")
        try:
            value = float(m.group(1).replace(",", "")) * _MAGNITUDES.get(m.group(2) or "", 1)
        except ValueError:
            continue
        out.append(Quantity(
            value, unit, roles[0] if len(roles) == 1 else "", m.group(0).strip(), nouns[0] if nouns else "",
        ))
    return out


_TO_BANGLA_DIGITS = str.maketrans("0123456789", "০১২৩৪৫৬৭৮৯")


def _bangla_digits(text: str) -> str:
    return text.translate(_TO_BANGLA_DIGITS)


def _same_value(a: Quantity, b: Quantity) -> bool:
    return abs(a.value - b.value) <= 1e-9 * max(1.0, abs(a.value))


def _quantity_supported(q: Quantity, pool: list[Quantity]) -> bool:
    return any(
        _same_value(q, e)
        and (not q.role or not e.role or q.role == e.role)
        and (not q.unit or not e.unit or q.unit == e.unit)
        for e in pool
    )


def _quantity_conflict(q: Quantity, claim_qs: list[Quantity], sentence_qs: list[Quantity]) -> Quantity | None:
    """The single source quantity about the same referent, when it differs."""
    if q.role:
        comparable = [
            e for e in sentence_qs
            if e.role == q.role
            and (not q.unit or not e.unit or e.unit == q.unit or {q.unit, e.unit} <= _CURRENCIES)
        ]
    elif q.noun:
        comparable = [
            e for e in sentence_qs
            if not e.role and e.noun == q.noun and (not q.unit or not e.unit or e.unit == q.unit)
        ]
    elif q.unit and q.unit not in _TIME_UNITS and sum(c.unit == q.unit for c in claim_qs) == 1:
        comparable = [e for e in sentence_qs if e.unit == q.unit]
    else:
        return None
    if len(comparable) != 1:
        return None
    e = comparable[0]
    if _same_value(q, e) and (not q.unit or not e.unit or q.unit == e.unit):
        return None
    return e


# ── comparison ───────────────────────────────────────────────────────────


@dataclass
class _Unit:
    """One piece of source evidence: the title or one body sentence."""

    location: str
    text: str
    quote: str  # the sentence with its neighbours, verbatim
    tokens: list[str]
    keys: set[str]
    quote_keys: set[str]
    qty: list[Quantity]
    quote_qty: list[Quantity]


def _unit(location: str, text: str, quote: str) -> _Unit:
    return _Unit(
        location, text, quote, tokenize(text), _evidence_keys(text), _evidence_keys(quote),
        quantities(text), quantities(quote),
    )


@dataclass
class _Pair:
    status: str
    units: list[_Unit]
    alignment: float
    explanation: str
    kind: str = "none"
    basis: str = "none"
    nli: dict[str, float] = field(default_factory=dict)
    meta: dict[str, str] = field(default_factory=dict)
    hard: bool = False  # an INSUFFICIENT pair blocked by a factual difference


@dataclass
class _Run:
    units: list[_Unit]
    claim_mentions: list[EntityMention] = field(default_factory=list)
    source_mentions: list[EntityMention] = field(default_factory=list)
    ner_ok: bool = False
    nli_cache: dict = field(default_factory=dict)
    nli_calls: int = 0


_VERBATIM_EXPLANATION = {
    "title": "The source title states this verbatim.",
    "body": "The source text states this verbatim.",
}


class ContentComparator:
    """Local claim/evidence comparison shared by every claim type."""

    def __init__(self, embedding_service, nli_service, ner_service, *, nli_validated: bool | None = None) -> None:
        self.embedder, self.nli, self.ner = embedding_service, nli_service, ner_service
        self.nli_validated = (
            get_settings().classification.nli_bangla_validated if nli_validated is None else nli_validated
        )

    async def compare(
        self, headline: str, body: str | None, title: str, source_body: str
    ) -> ContentCheck:
        ml = get_settings().ml
        check = ContentCheck(
            method=METHOD,
            models=f"local:{ml.embedding_model_name}|{ml.nli_model_name}|{ml.ner_model_name}",
            nli_reliability="VALIDATED_FOR_BANGLA" if self.nli_validated else "UNVALIDATED_FOR_BANGLA",
        )
        statements = self._statements(headline, body)
        if not any(part == "headline" for part, _ in statements):
            check.reason = "The headline contains no comparable statement."
            return check
        if len(statements) > MAX_STATEMENTS:
            check.unchecked_statements = len(statements) - MAX_STATEMENTS
            statements = statements[:MAX_STATEMENTS]

        units, check.source_truncated = self._source_units(title or "", source_body or "")
        if not units:
            check.reason = "The source report has no extracted title or text to compare with."
            return check

        sims = await self._similarities([t for _, t in statements], units)
        candidates = [self._candidates(text, units, sims[i] if sims is not None else None)
                      for i, (_, text) in enumerate(statements)]
        run = _Run(units)
        await self._load_mentions(run, statements, {j for c in candidates for j, _ in c})
        for (part, text), cands in zip(statements, candidates):
            check.findings.append(await self._statement(part, text, cands, run))
        logger.info(
            "content_check_complete",
            statements=len(statements),
            status={s: sum(f.status == s for f in check.findings) for s in (SUPPORTED, CONTRADICTED, INSUFFICIENT)},
            nli_calls=run.nli_calls,
            ner_ok=run.ner_ok,
        )
        return check

    # ── inputs ──────────────────────────────────────────────────────────

    @staticmethod
    def _statements(headline: str, body: str | None) -> list[tuple[str, str]]:
        # Line breaks in a headline (photo-card layout) do not end a statement.
        out = [
            ("headline", s)
            for _, _, s in split_statements(re.sub(r"\s*\n\s*", " ", headline or ""))
            if _content_units(s) or quantities(s)
        ]
        seen: set[tuple[str, ...]] = set()
        for _, _, s in split_statements(body):
            key = tuple(tokenize(s))
            if not key or key in seen or _BOILERPLATE_RE.match(s) or _DATELINE_RE.match(_n(s)):
                continue
            # Datelines, bylines and fragments are not material statements.
            if len(_content_units(s)) < 2 and not quantities(s):
                continue
            seen.add(key)
            out.append(("body", s))
        return out

    @staticmethod
    def _source_units(title: str, body: str) -> tuple[list[_Unit], bool]:
        units = [_unit("title", title.strip(), title.strip())] if title.strip() else []
        spans = split_statements(body)
        truncated = len(spans) > MAX_SOURCE_SENTENCES
        spans = spans[:MAX_SOURCE_SENTENCES]
        for i, (start, end, sentence) in enumerate(spans):
            lo = spans[i - 1][0] if i else start
            hi = spans[i + 1][1] if i + 1 < len(spans) else end
            quote = body[lo:hi].strip()
            units.append(_unit("body", sentence, quote if len(quote) <= NLI_PREMISE_CHARS else sentence))
        return units, truncated

    async def _similarities(self, texts: list[str], units: list[_Unit]):
        """Local embedding similarity, used only to choose evidence."""
        try:
            vectors = await self.embedder.encode_batch(texts + [u.text for u in units])
            matrix = np.asarray(vectors[: len(texts)]) @ np.asarray(vectors[len(texts) :]).T
            if matrix.shape != (len(texts), len(units)) or not np.isfinite(matrix).all():
                raise ValueError("invalid local embeddings")
            return matrix
        except Exception as exc:  # noqa: BLE001 - selection falls back to words
            logger.warning("content_check_embeddings_unavailable", error=str(exc))
            return None

    @staticmethod
    def _candidates(text: str, units: list[_Unit], sims) -> list[tuple[int, float]]:
        content = _content_units(text)
        scored = []
        for j, u in enumerate(units):
            cov = _coverage(content, u.keys)
            sem = float(sims[j]) if sims is not None else 0.0
            if cov >= ALIGN_CANDIDATE or sem >= SEM_CANDIDATE:
                scored.append((j, cov, (cov + sem) / 2 if sims is not None else cov))
        scored.sort(key=lambda x: x[2], reverse=True)
        return [(j, cov) for j, cov, _ in scored[:MAX_CANDIDATES]]

    async def _load_mentions(self, run: _Run, statements, unit_ids: set[int]) -> None:
        """Typed entities of the claim and of the candidate source passages,
        found once (NER runs on bounded batches, never a truncated whole)."""
        if self.ner is None:
            return
        claims, claims_ok = await self._mentions([t for _, t in statements])
        sources, sources_ok = await self._mentions(
            list(dict.fromkeys(run.units[j].quote for j in sorted(unit_ids)))
        )
        run.claim_mentions, run.source_mentions = claims, sources
        run.ner_ok = claims_ok and sources_ok

    async def _mentions(self, texts: list[str]) -> tuple[list[EntityMention], bool]:
        mentions: dict[tuple, EntityMention] = {}
        batch: list[str] = []
        ok = True

        async def flush():
            nonlocal ok
            if not batch:
                return
            result = await self.ner.extract_mentions("\n".join(batch))
            ok = ok and result.available and not result.truncated
            for m in result.mentions:
                mentions.setdefault((m.key, m.type), m)
            batch.clear()

        try:
            for text in texts:
                if batch and sum(len(t) + 1 for t in batch) + len(text) > NER_BATCH_CHARS:
                    await flush()
                batch.append(text)
            await flush()
        except Exception as exc:  # noqa: BLE001
            logger.warning("content_check_ner_unavailable", error=str(exc))
            return [], False
        return list(mentions.values()), ok

    async def _nli(self, claim: str, u: _Unit, run: _Run) -> dict[str, float] | None:
        if len(claim) > NLI_HYPOTHESIS_CHARS or self.nli is None:
            return None
        premise = u.quote if len(u.quote) <= NLI_PREMISE_CHARS else u.text
        if len(premise) > NLI_PREMISE_CHARS:
            return None
        key = (premise, claim)
        if key not in run.nli_cache:
            if run.nli_calls >= MAX_NLI_CALLS:
                return None
            run.nli_calls += 1
            try:
                scores = await self.nli.predict(premise=premise, hypothesis=claim)
            except Exception:  # noqa: BLE001
                scores = None
            run.nli_cache[key] = (
                {k: round(float(v), 4) for k, v in scores.model_dump().items()} if scores is not None else None
            )
        return run.nli_cache[key]

    # ── one statement ───────────────────────────────────────────────────

    async def _statement(self, part: str, text: str, cands, run: _Run) -> ContentFinding:
        pair = await self._evaluate(text, cands, run)
        if pair.status == INSUFFICIENT:
            pair = await self._by_clauses(text, run) or pair
        return self._finding(part, text, pair, run)

    async def _evaluate(self, text: str, cands, run: _Run) -> _Pair:
        content, toks = _content_units(text), tokenize(text)
        for u in run.units:
            if (not content or _coverage(content, u.keys) == 1.0) and _verbatim(toks, u.tokens):
                return _Pair(SUPPORTED, [u], 1.0, _VERBATIM_EXPLANATION[u.location], basis="verbatim")
        pairs = [await self._pair(text, run.units[j], cov, run) for j, cov in cands]
        return self._combine(pairs)

    async def _by_clauses(self, text: str, run: _Run) -> _Pair | None:
        """A statement joining facts from different source sentences
        (headline = title + a lead detail) is supported when each clause is."""
        clauses = [c for c in _clauses(text) if len(_content_units(c)) >= 2 or (_content_units(c) and quantities(c))]
        if len(clauses) < 2:
            return None
        results = [await self._evaluate(c, self._candidates(c, run.units, None), run) for c in clauses]
        contradicted = [r for r in results if r.status == CONTRADICTED]
        if contradicted:
            return contradicted[0]
        if all(r.status == SUPPORTED for r in results):
            units = list({id(u): u for r in results for u in r.units}.values())
            return _Pair(
                SUPPORTED, units, min(r.alignment for r in results),
                "Each part of this statement is supported by the source: "
                + " ".join(f'"{c}" — {r.explanation}' for c, r in zip(clauses, results)),
                basis="clauses",
            )
        return None

    async def _pair(self, claim: str, u: _Unit, cov: float, run: _Run) -> _Pair:
        content, qs = _content_units(claim), quantities(claim)
        if cov >= ALIGN_CONFLICT and (len(content) >= 2 or qs):
            conflict = self._conflict(claim, qs, u, cov, run)
            if conflict is not None:
                if conflict.kind in {"modality", "scope"}:
                    # Heuristic rules: a confident local reading of the two as
                    # equivalent leaves the case open rather than ALTERED.
                    nli = await self._nli(claim, u, run)
                    if nli and nli["entailment"] >= STRONG_ENTAILMENT:
                        return _Pair(
                            INSUFFICIENT, [u], cov,
                            f"{conflict.explanation} The local semantic model reads the two as equivalent, so this is unresolved.",
                            nli=nli, hard=True,
                        )
                    conflict.nli = nli or {}
                return conflict

        problems = self._problems(claim, content, qs, u, run)
        if not problems:
            return _Pair(
                SUPPORTED, [u], cov,
                "Every word, number and name of this statement is in the source passage, "
                "with the same negation, tense and quantifiers.",
                basis="facts_preserved",
            )
        hard = [p for h, p in problems if h]
        nli = await self._nli(claim, u, run)
        if nli is not None:
            if self.nli_validated and nli["contradiction"] >= VALIDATED_CONTRADICTION_MIN and cov >= ALIGN_CONFLICT:
                return _Pair(
                    CONTRADICTED, [u], cov,
                    "The validated local NLI model finds that the source passage contradicts this statement.",
                    kind="semantic", basis="conflict", nli=nli,
                )
            if (
                nli["entailment"] >= ENTAILMENT_MIN
                and nli["contradiction"] <= NLI_SUPPORT_MAX_CONTRADICTION
                and not hard
            ):
                return _Pair(
                    SUPPORTED, [u], cov,
                    "The source passage expresses the same meaning (local NLI entailment), "
                    "and the statement's numbers and names are in it.",
                    basis="entailment", nli=nli,
                )
        reason = (hard or [p for _, p in problems])[0]
        if nli is None and not hard:
            reason += " A paraphrase could not be confirmed because local semantic comparison was unavailable."
        elif not hard:
            reason += " The local semantic model does not establish the same meaning."
        return _Pair(INSUFFICIENT, [u], cov, reason, nli=nli or {}, hard=bool(hard))

    def _conflict(self, claim: str, qs: list[Quantity], u: _Unit, cov: float, run: _Run) -> _Pair | None:
        """A concrete, quotable difference from a sentence about the same thing."""

        def found(kind: str, detail: str, meta: dict | None = None) -> _Pair:
            return _Pair(CONTRADICTED, [u], cov, detail, kind=kind, basis="conflict", meta=meta or {})

        for q in qs:
            if _quantity_supported(q, u.quote_qty):
                continue
            e = _quantity_conflict(q, qs, u.qty)
            if e is not None:
                what = f"{q.role or q.noun}: " if q.role or q.noun else ""
                claimed, stated = _bangla_digits(q.surface), _bangla_digits(e.surface)
                if _same_value(q, e):
                    return found("numbers", f"{what}the claim uses {q.unit}, the source uses {e.unit}.",
                                 {"claimed": claimed, "source": stated})
                return found("numbers", f"{what}claimed {claimed}, the source states {stated}.",
                             {"claimed": claimed, "source": stated})

        aligned, _ = _clause_alignment(claim, u.text)
        for cc, ec, _, ambiguous in aligned:
            if ambiguous or len(_content_units(cc)) < 2:
                continue
            if _polarity(cc) != _polarity(ec) and _same_predicate(cc, ec):
                return found(
                    "negation",
                    "The claim negates what the source affirms." if _polarity(cc)
                    else "The claim affirms what the source negates.",
                )
            if _modality_conflict(cc, ec):
                return found(
                    "modality",
                    "The claim reports a completed event; the source describes a plan, possibility or future event."
                    if _modality(cc) == "COMPLETED"
                    else "The claim describes a plan or possibility; the source reports it as completed.",
                )
            if _scope_conflict(cc, ec):
                return found(
                    "scope",
                    f"The quantifier differs (claim: {', '.join(sorted(qualifier_groups(cc)))}; "
                    f"source: {', '.join(sorted(qualifier_groups(ec)))}).",
                )

        if run.ner_ok:
            claimed = mentions_in_sentence(claim, run.claim_mentions)
            if claimed:
                quote_mentions = mentions_in_sentence(u.quote, run.source_mentions)
                quote_keys = tuple(light_stem(t) for t in tokenize(u.quote))
                result = check_entities(
                    [Alignment(ClaimSentence(claim, "headline"), [(EvidenceSentence(u.text, u.location), cov)])],
                    claimed, mentions_in_sentence(u.text, run.source_mentions), ner_available=True,
                )
                for d in result.discrepancies:
                    if d.kind == "entity_substitution":
                        # The claimed name may appear in a neighbouring sentence.
                        m = next((m for m in claimed if m.text == d.meta.get("claimed")), None)
                        if m is not None and match_entity(m, quote_mentions, quote_keys).matched:
                            continue
                    return found(d.kind, d.detail[:1].upper() + d.detail[1:] + ".",
                                 {k: str(v) for k, v in d.meta.items()})

        if _drops_allegation(claim, u.text):
            return found(
                "attribution",
                "The source reports this as someone's claim or allegation; the statement presents it as established fact.",
            )
        return None

    def _problems(self, claim: str, content, qs: list[Quantity], u: _Unit, run: _Run) -> list[tuple[bool, str]]:
        """What keeps the passage from establishing the statement on facts
        alone: (hard, reason). Hard problems also block NLI-based support."""
        problems: list[tuple[bool, str]] = []
        missing = [x.text for x in content if not ({x.text, light_stem(x.text)} & u.quote_keys)]
        if missing:
            problems.append((False, f"The source passage does not contain: {', '.join(missing[:6])}."))
        absent_numbers = [q.surface for q in qs if not _quantity_supported(q, u.quote_qty)]
        if absent_numbers:
            problems.append((
                True, f"The source passage does not state {', '.join(map(_bangla_digits, absent_numbers))} for this.",
            ))
        if run.ner_ok:
            quote_mentions = mentions_in_sentence(u.quote, run.source_mentions)
            quote_keys = tuple(light_stem(t) for t in tokenize(u.quote))
            absent = [
                m.text for m in mentions_in_sentence(claim, run.claim_mentions)
                if not match_entity(m, quote_mentions, quote_keys).matched
            ]
            if absent:
                problems.append((True, f"The source passage does not name {', '.join(absent)}."))
        aligned, unaligned = _clause_alignment(claim, u.quote)
        for cc, ec, _, ambiguous in aligned:
            if ambiguous:
                problems.append((False, "The source passage states this both ways."))
            elif _polarity(cc) != _polarity(ec) and not _same_predicate(cc, ec):
                problems.append((False, "The source passage does not state this action."))
            elif _polarity(cc) != _polarity(ec):
                problems.append((True, "The negation differs from the source passage."))
            elif _modality_conflict(cc, ec):
                problems.append((True, "Planned/possible versus completed differs from the source passage."))
            elif _scope_conflict(cc, ec):
                problems.append((True, "The quantifier differs from the source passage."))
        if unaligned:
            problems.append((False, "Parts of the statement are not stated together in the source passage."))
        if _role_flip(claim, u.quote):
            problems.append((True, "Who did what to whom appears reversed relative to the source passage."))
        if _denies(u.text) and not _denies(claim):
            problems.append((True, "The source passage disputes or denies this."))
        if _drops_allegation(claim, u.text):
            problems.append((True, "The source attributes this to someone's claim or allegation."))
        if len(content) < 2 and not qs:
            problems.append((False, "The statement is too short to establish from its wording alone."))
        return problems

    @staticmethod
    def _combine(pairs: list[_Pair]) -> _Pair:
        """One verdict per statement from its candidate passages. Absence is
        never contradiction; a contradiction must come from (one of) the most
        closely matching passages."""
        if not pairs:
            return _Pair(INSUFFICIENT, [], 0.0, "No passage of the source report discusses this statement.")
        best = max(p.alignment for p in pairs)
        supported = [p for p in pairs if p.status == SUPPORTED]
        contradicted = [p for p in pairs if p.status == CONTRADICTED and p.alignment >= best - TIE_BAND]
        if supported:
            s = max(supported, key=lambda p: (p.alignment, p.units[0].location == "title"))
            c = max(contradicted, key=lambda p: p.alignment, default=None)
            if c is not None and c.alignment > s.alignment:
                return _Pair(
                    INSUFFICIENT, s.units + c.units, s.alignment,
                    "The source contains competing statements: one supports this, "
                    f"a more closely matching one differs ({c.explanation})",
                    hard=True,
                )
            return s
        if contradicted:
            return max(contradicted, key=lambda p: p.alignment)
        return max(pairs, key=lambda p: (p.hard, p.alignment))

    def _finding(self, part: str, text: str, pair: _Pair, run: _Run) -> ContentFinding:
        evidence = [
            ContentEvidence(location=u.location, quote=u.text if pair.basis == "verbatim" else u.quote)
            for u in pair.units[:6]
        ]
        return ContentFinding(
            part=part, claim_text=text, status=pair.status, kind=pair.kind, basis=pair.basis,
            explanation=pair.explanation, evidence=evidence, checks=self._checks(text, run),
            alignment=round(pair.alignment, 4), nli=pair.nli, meta=pair.meta,
        )

    @staticmethod
    def _checks(text: str, run: _Run) -> list[str]:
        toks = set(tokenize(text))
        checks = ["negation"]
        if quantities(text) or re.search(r"[0-9০-৯]", text):
            checks.append("numbers")
        if run.ner_ok and mentions_in_sentence(text, run.claim_mentions):
            checks.append("entities")
        if qualifier_groups(text):
            checks.append("scope")
        if toks & _ATTRIBUTION_WORDS:
            checks.append("attribution")
        if _modality(text) != "UNKNOWN":
            checks.append("modality")
        return checks


# ── result presentation ──────────────────────────────────────────────────

_CHECK_FOR_KIND = {
    "numbers": "numbers", "negation": "negation", "entity_substitution": "entities",
    "entity_role": "entities", "scope": "scope", "attribution": "attribution", "modality": "modality",
}


def content_flags(check: ContentCheck, *, with_body: bool) -> tuple[ManipulationFlagsSchema, list[ManipulationType]]:
    """Per-part and per-fact-type check states plus the quotable discrepancies."""
    findings = check.findings
    contradicted = [f for f in findings if f.status == CONTRADICTED]

    def part_state(part: str) -> CheckState:
        fs = [f for f in findings if f.part == part]
        if any(f.status == CONTRADICTED for f in fs):
            return CheckState.FAILED
        complete = part == "headline" or not check.unchecked_statements
        if fs and complete and all(f.status == SUPPORTED for f in fs):
            return CheckState.PASSED
        return CheckState.NOT_EVALUATED

    states: dict[str, CheckState] = {
        "headline": part_state("headline"),
        "body": part_state("body") if with_body else CheckState.NOT_APPLICABLE,
    }
    for name in ("numbers", "negation", "entities", "scope", "attribution", "modality"):
        if any(_CHECK_FOR_KIND.get(f.kind) == name for f in contradicted):
            states[name] = CheckState.FAILED
            continue
        relevant = [f for f in findings if name in f.checks]
        if relevant:
            states[name] = (
                CheckState.PASSED if all(f.status == SUPPORTED for f in relevant) else CheckState.NOT_EVALUATED
            )

    flags = ManipulationFlagsSchema(
        headline_manipulated=any(f.part == "headline" for f in contradicted),
        body_altered=with_body and any(f.part == "body" for f in contradicted),
        numbers_altered=states.get("numbers") == CheckState.FAILED,
        entities_replaced=states.get("entities") == CheckState.FAILED,
        altered_numbers=[
            AlteredNumberDetail(claimed=f.meta.get("claimed", ""), nearest_in_article=f.meta.get("source"))
            for f in contradicted if f.kind == "numbers"
        ],
        substituted_entities=[
            SubstitutedEntityDetail(
                entity_type=f.meta.get("type", ""),
                claimed=[f.meta.get("claimed", "")],
                article_same_type=[f.meta.get("source", "")],
            )
            for f in contradicted if f.kind == "entity_substitution"
        ],
        check_states=states,
        discrepancies=[
            DiscrepancyDetail(
                kind=f.kind, claim_text=f.claim_text,
                evidence_text="\n".join(e.quote for e in f.evidence) or None,
                detail=f.explanation, part=f.part,
            )
            for f in contradicted
        ],
    )
    detected: list[ManipulationType] = []
    if flags.headline_manipulated:
        detected.append(ManipulationType.HEADLINE_MANIPULATED)
    if flags.body_altered:
        detected.append(ManipulationType.BODY_ALTERED)
    if flags.numbers_altered:
        detected.append(ManipulationType.NUMBERS_ALTERED)
    if flags.entities_replaced:
        detected.append(ManipulationType.ENTITIES_REPLACED)
    return flags, detected
