from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from app.core.constants import DateStatus, MetricState, SourceStatus


@dataclass
class Metric:
    state: MetricState = MetricState.UNAVAILABLE
    value: float | None = None

    @property
    def ok(self) -> bool:
        return self.state == MetricState.COMPUTED and self.value is not None


@dataclass
class CorrespondenceInputs:
    headline_title_similarity: Metric = field(default_factory=Metric)
    title_keyword_coverage: Metric = field(default_factory=Metric)
    passage_keyword_coverage: Metric = field(default_factory=Metric)


@dataclass
class Correspondence:
    level: str
    basis: list[str] = field(default_factory=list)


def assess_correspondence(inp: CorrespondenceInputs, t) -> Correspondence:
    h = inp.headline_title_similarity.value if inp.headline_title_similarity.ok else None
    kt = inp.title_keyword_coverage.value if inp.title_keyword_coverage.ok else None
    kp = inp.passage_keyword_coverage.value if inp.passage_keyword_coverage.ok else None

    if h is None and kt is None and kp is None:
        return Correspondence("UNKNOWN", ["no similarity or keyword measurement was available"])

    title_support = kt is not None and kt >= t.corr_keyword_title_plausible
    passage_support = kp is not None and kp >= t.corr_keyword_passage_plausible

    if h is not None:
        if h >= t.corr_headline_sim_alone:
            return Correspondence("STRONG", [f"headline/title similarity {h:.2f} ≥ {t.corr_headline_sim_alone:.2f}"])
        if h >= t.corr_headline_sim_strong and title_support:
            return Correspondence("STRONG", [
                f"headline/title similarity {h:.2f} ≥ {t.corr_headline_sim_strong:.2f}",
                f"claim keywords found in the source title ({kt:.2f})",
            ])
        if h >= t.corr_headline_sim_plausible and (title_support or passage_support):
            return Correspondence("PLAUSIBLE", [
                f"headline/title similarity {h:.2f} ≥ {t.corr_headline_sim_plausible:.2f}",
                "claim keywords found in the source "
                + ("title" if title_support else "passages that discuss the claim"),
            ])
        return Correspondence("NONE", [
            f"headline/title similarity {h:.2f}",
            "the claim's own keywords are not sufficiently present in the retrieved article",
        ])

    if kt is not None and kt >= t.corr_keyword_only_title:
        return Correspondence("PLAUSIBLE", ["strong title keyword coverage (similarity model unavailable)"])
    return Correspondence("NONE", ["weak keyword coverage and no similarity measurement"])


def decide_source(
    *,
    has_evidence: bool,
    search_adequate: bool | None,
    retrieval_failed: bool,
    correspondence: Correspondence | None,
    blocked_match: str | None = None,
) -> tuple[SourceStatus, list[str]]:
    blocked = (
        [f"a search result matching the claim ({blocked_match}) could not be retrieved - "
         "the site blocked automated access"]
        if blocked_match
        else []
    )
    if not has_evidence:
        if retrieval_failed:
            return SourceStatus.INCOMPLETE, ["candidate pages could not be fetched or extracted"] + blocked
        if blocked:
            return SourceStatus.INCOMPLETE, blocked
        if search_adequate:
            return SourceStatus.NOT_FOUND, ["an adequate search completed and returned no article from the claimed source"]
        return SourceStatus.INCOMPLETE, ["the search did not complete adequately (provider failures or too few completed calls)"]

    assert correspondence is not None
    if blocked:
        return SourceStatus.INCOMPLETE, correspondence.basis + blocked
    if correspondence.level in {"STRONG", "PLAUSIBLE"}:
        return SourceStatus.CONFIRMED, correspondence.basis
    if correspondence.level == "UNKNOWN":
        return SourceStatus.INCOMPLETE, correspondence.basis
    if search_adequate:
        return SourceStatus.NOT_FOUND, correspondence.basis + [
            "an adequate search found no corresponding report from the claimed source"
        ]
    return SourceStatus.INCOMPLETE, correspondence.basis + [
        "the search was not adequate, so absence of a corresponding report is not established"
    ]


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
    if attempted <= 0 or completed < min_calls:
        return False
    return (completed / attempted) >= min_ratio


def correspondence_strength(values: list[float | None]) -> float:
    present = [v for v in values if v is not None]
    return round(sum(present) / len(present), 3) if present else 0.0
