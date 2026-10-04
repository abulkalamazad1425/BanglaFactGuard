"""Source / Content / Date decisions as pure functions.

The three dimensions are decided separately and from different evidence:

* SOURCE   — did the claimed outlet publish a corresponding report?
             (article correspondence + search adequacy; NOT content match)
* CONTENT  — does the claim carry the same material facts as that report?
             (statement-by-statement evidence; a similarity score never
             decides it either way)
* DATE     — does the claimed day equal the report's datePublished day in
             Asia/Dhaka? (independent of content)

Scores are measurements, not probabilities. Nothing here turns a weak or
missing measurement into ALTERED or NOT_FOUND; those need a completed search
or a concrete discrepancy.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from typing import TYPE_CHECKING

from app.core.constants import (
    ClaimScope,
    ContentStatus,
    DateStatus,
    MetricState,
    SourceStatus,
)

if TYPE_CHECKING:
    from app.features.verification.schemas import ContentCheck


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
    headline_keyword_coverage: Metric = field(default_factory=Metric)
    passage_keyword_coverage: Metric = field(default_factory=Metric)
    body_similarity: Metric = field(default_factory=Metric)
    entity_coverage: Metric = field(default_factory=Metric)


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


def decide_content(check: ContentCheck) -> tuple[ContentStatus, list[str]]:
    """Content from the statement-by-statement comparison (see
    `analysis/content_check.py`).

    ALTERED   at least one material statement has a concrete, quotable
              difference from the source.
    MATCHED   every material statement is supported: verbatim, condensed
              with its facts preserved, or a faithful paraphrase.
    INCOMPLETE otherwise: the evidence needed is missing or genuinely
              ambiguous. A low score alone never leads here, and absence
              from the source is never ALTERED.
    """
    if check.reason:
        return ContentStatus.INCOMPLETE, [check.reason]
    contradicted = [f for f in check.findings if f.status == "CONTRADICTED"]
    if contradicted:
        return ContentStatus.ALTERED, [_describe(f) for f in contradicted]
    open_ = [f for f in check.findings if f.status != "SUPPORTED"]
    if check.findings and not open_ and not check.unchecked_statements:
        shown = check.findings[:_MAX_BASIS]
        basis = [_describe(f) for f in shown]
        if len(check.findings) > len(shown):
            basis.append(f"{len(check.findings) - len(shown)} more statement(s) likewise supported")
        return ContentStatus.MATCHED, basis
    basis = [_describe(f) for f in open_[:_MAX_BASIS]]
    if len(open_) > _MAX_BASIS:
        basis.append(f"{len(open_) - _MAX_BASIS} more statement(s) not established")
    if check.unchecked_statements:
        basis.append(
            f"{check.unchecked_statements} submitted statement(s) exceeded the comparison limit and were not compared"
        )
    return ContentStatus.INCOMPLETE, basis


_MAX_BASIS = 6


def _describe(finding) -> str:
    claim = finding.claim_text if len(finding.claim_text) <= 90 else finding.claim_text[:87] + "..."
    return f'{finding.part} "{claim}": {finding.explanation.rstrip(". ")}'


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
