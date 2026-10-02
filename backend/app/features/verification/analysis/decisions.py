"""Source / Content / Date decisions as pure functions.

The three dimensions are decided separately and from different evidence:

* SOURCE   — did the claimed outlet publish a corresponding report?
             (article correspondence + search adequacy; NOT content match)
* CONTENT  — does the claim carry the same material facts as that report?
             (concrete discrepancies, positive support; never "similarity
             was low")
* DATE     — does the claimed day equal the report's datePublished day in
             Asia/Dhaka? (independent of content)

Scores are measurements, not probabilities. Nothing here turns a weak or
missing measurement into ALTERED or NOT_FOUND; those need a completed search
or a concrete discrepancy.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from app.core.constants import (
    CheckState,
    ClaimScope,
    ContentStatus,
    DateStatus,
    MetricState,
    SourceStatus,
)


@dataclass
class Metric:
    """A score plus the state that explains it."""

    state: MetricState = MetricState.UNAVAILABLE
    value: float | None = None

    @property
    def ok(self) -> bool:
        return self.state == MetricState.COMPUTED and self.value is not None


@dataclass
class DecisionInputs:
    scope: ClaimScope
    headline_similarity: Metric = field(default_factory=Metric)
    passage_similarity: Metric = field(default_factory=Metric)
    headline_keyword_coverage: Metric = field(default_factory=Metric)
    passage_keyword_coverage: Metric = field(default_factory=Metric)
    body_similarity: Metric = field(default_factory=Metric)
    body_min_chunk_similarity: float | None = None
    body_keyword_coverage: Metric = field(default_factory=Metric)
    body_complete: bool = True
    entity_coverage: Metric = field(default_factory=Metric)
    check_states: dict[str, CheckState] = field(default_factory=dict)
    discrepancy_count: int = 0
    contradiction: float | None = None
    nli_premise_is_passages: bool = False


@dataclass
class Correspondence:
    level: str  # STRONG | PLAUSIBLE | NONE | UNKNOWN
    basis: list[str] = field(default_factory=list)


def assess_correspondence(inp: DecisionInputs, t) -> Correspondence:
    """Is the retrieved article plausibly THE report the claim is about?

    Uses headline-to-title similarity and lexical support only — body
    metrics and the alteration checks are deliberately excluded so that an
    altered detail (or a defective aggregate score) cannot make a genuine
    original report look like a different article.
    """
    h = inp.headline_similarity.value if inp.headline_similarity.ok else None
    kt = inp.headline_keyword_coverage.value if inp.headline_keyword_coverage.ok else None
    kp = inp.passage_keyword_coverage.value if inp.passage_keyword_coverage.ok else None
    lexical = max([v for v in (kt, kp) if v is not None], default=None)

    if h is None and lexical is None:
        return Correspondence("UNKNOWN", ["no similarity or keyword measurement was available"])

    if h is not None and h >= t.corr_headline_sim_strong:
        return Correspondence("STRONG", [f"headline↔title similarity {h:.2f} ≥ {t.corr_headline_sim_strong:.2f}"])

    if h is not None:
        lexical_ok = (kt is not None and kt >= t.corr_keyword_title_plausible) or (
            kp is not None and kp >= t.corr_keyword_passage_plausible
        )
        if h >= t.corr_headline_sim_plausible and lexical_ok:
            return Correspondence(
                "PLAUSIBLE",
                [
                    f"headline↔title similarity {h:.2f} ≥ {t.corr_headline_sim_plausible:.2f}",
                    "claim keywords found in the source title/passages",
                ],
            )
        return Correspondence(
            "NONE",
            [
                f"headline↔title similarity {h:.2f}",
                "claim keywords not sufficiently present in the retrieved article",
            ],
        )

    # No embedding similarity: lexical evidence alone must be strong.
    if (kt is not None and kt >= t.corr_keyword_only_title) or (
        kp is not None and kp >= t.corr_keyword_only_title
    ):
        return Correspondence("PLAUSIBLE", ["strong keyword coverage (similarity model unavailable)"])
    return Correspondence("NONE", ["weak keyword coverage and no similarity measurement"])


def decide_source(
    *,
    has_evidence: bool,
    search_adequate: bool | None,
    retrieval_failed: bool,
    correspondence: Correspondence | None,
) -> tuple[SourceStatus, list[str]]:
    """CONFIRMED needs a corresponding report; NOT_FOUND needs an ADEQUATE
    search that came up without one; everything else is INCOMPLETE."""
    if not has_evidence:
        if retrieval_failed:
            return SourceStatus.INCOMPLETE, ["candidate pages could not be fetched or extracted"]
        if search_adequate:
            return SourceStatus.NOT_FOUND, ["an adequate search completed and returned no article from the claimed source"]
        return SourceStatus.INCOMPLETE, ["the search did not complete adequately (provider failures or too few completed calls)"]

    assert correspondence is not None
    if correspondence.level in {"STRONG", "PLAUSIBLE"}:
        return SourceStatus.CONFIRMED, correspondence.basis
    if correspondence.level == "UNKNOWN":
        return SourceStatus.INCOMPLETE, correspondence.basis
    # level NONE: retrieved articles do not correspond.
    if search_adequate:
        return SourceStatus.NOT_FOUND, correspondence.basis + [
            "an adequate search found no corresponding report from the claimed source"
        ]
    return SourceStatus.INCOMPLETE, correspondence.basis + [
        "the search was not adequate, so absence of a corresponding report is not established"
    ]


def decide_content(
    inp: DecisionInputs, t, *, concrete_failures: int
) -> tuple[ContentStatus, list[str]]:
    """ALTERED only on a concrete discrepancy (or reliable contradiction).
    MATCHED only on positive support for every applicable material claim.
    Anything else is INCOMPLETE — never an automatic ALTERED."""
    if concrete_failures > 0:
        return ContentStatus.ALTERED, [
            f"{concrete_failures} concrete discrepancy(ies) between the claim and the source report"
        ]

    if (
        t.nli_bangla_validated
        and inp.nli_premise_is_passages
        and inp.contradiction is not None
        and inp.contradiction >= t.contradiction_override_threshold
    ):
        return ContentStatus.ALTERED, [
            f"validated NLI contradiction {inp.contradiction:.2f} against the relevant passages"
        ]

    missing: list[str] = []
    support: list[str] = []

    # Headline support
    h = inp.headline_similarity
    kt = inp.headline_keyword_coverage
    kw_needed = t.support_keyword_coverage
    ent = inp.entity_coverage
    if ent.state == MetricState.UNAVAILABLE:
        # Entities cannot be checked directly; require stricter lexical coverage
        # (names are keywords) and say so.
        kw_needed = t.support_keyword_coverage_no_ner
        missing_note = "entity coverage unavailable (NER) — stricter keyword coverage required"
    else:
        missing_note = None

    if h.ok and h.value >= t.support_headline_sim:
        support.append(f"headline similarity {h.value:.2f}")
    elif h.ok and inp.passage_similarity.ok and inp.passage_similarity.value >= t.support_headline_sim:
        support.append(f"passage similarity {inp.passage_similarity.value:.2f}")
    else:
        missing.append(
            "headline similarity below the support threshold"
            if h.ok
            else "headline similarity unavailable"
        )

    if kt.ok and kt.value >= kw_needed:
        support.append(f"headline keyword coverage {kt.value:.2f}")
    elif kt.state == MetricState.EMPTY:
        missing.append("claim yielded no keywords to compare")
    else:
        missing.append(
            f"headline keyword coverage {kt.value:.2f} below {kw_needed:.2f}"
            if kt.ok
            else "headline keyword coverage unavailable"
        )

    if ent.ok:
        if ent.value >= t.support_entity_coverage:
            support.append(f"entity coverage {ent.value:.2f}")
        else:
            missing.append(f"entity coverage {ent.value:.2f}: some claimed entities were not found in the source")
    elif missing_note:
        missing.append(missing_note)

    # Alteration checks that could not run block MATCHED (they are not passes).
    for name, state in inp.check_states.items():
        if state == CheckState.NOT_EVALUATED:
            missing.append(f"{name} check could not be evaluated")
        elif state == CheckState.PASSED:
            support.append(f"{name} check passed")

    # Body support only when a body was submitted.
    if inp.scope == ClaimScope.HEADLINE_WITH_BODY:
        b = inp.body_similarity
        body_missing: list[str] = []
        if not b.ok:
            body_missing.append("submitted-body comparison unavailable")
        else:
            if b.value < t.support_body_similarity:
                body_missing.append(f"body similarity {b.value:.2f} below {t.support_body_similarity:.2f}")
            if (
                inp.body_min_chunk_similarity is not None
                and inp.body_min_chunk_similarity < t.support_body_min_chunk_similarity
            ):
                body_missing.append("part of the submitted body has no close counterpart in the source")
            if inp.body_keyword_coverage.ok and inp.body_keyword_coverage.value < t.support_body_keyword_coverage:
                body_missing.append("submitted-body keywords are not covered by the source")
            if not inp.body_complete:
                body_missing.append("the submitted body was too long to compare in full")
            if not body_missing:
                support.append(f"body similarity {b.value:.2f}")
        missing.extend(body_missing)

    if inp.contradiction is not None and inp.contradiction >= t.possible_contradiction:
        missing.append(
            f"possible contradiction signal {inp.contradiction:.2f} from an NLI model not validated on Bangla"
        )

    if not missing:
        return ContentStatus.MATCHED, support
    return ContentStatus.INCOMPLETE, [f"not established: {m}" for m in missing]


def decide_date(
    claimed: date | None,
    article_date: date | None,
    *,
    source_confirmed: bool,
) -> DateStatus | None:
    if not source_confirmed or claimed is None:
        return None
    if article_date is None:
        return DateStatus.INCOMPLETE
    return DateStatus.MATCHED if claimed == article_date else DateStatus.MISMATCHED


def search_adequate(
    attempted: int,
    completed: int,
    *,
    min_calls: int,
    min_ratio: float,
) -> bool:
    """`completed` = SUCCESS + SUCCESS_EMPTY + CACHED provider calls."""
    if attempted <= 0 or completed < min_calls:
        return False
    return (completed / attempted) >= min_ratio


def check_strength(values: list[float | None]) -> float:
    """Mean of the applicable measurements (0.0 when there are none)."""
    present = [v for v in values if v is not None]
    return round(sum(present) / len(present), 3) if present else 0.0
