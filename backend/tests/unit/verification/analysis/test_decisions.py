"""Source and Date decisions. A failed or inadequate search is never a
confident NOT_FOUND."""

from datetime import date

import pytest

from app.core.config import get_settings
from app.core.constants import DateStatus, MetricState, SourceStatus
from app.features.verification.analysis.decisions import (
    Correspondence,
    CorrespondenceInputs,
    Metric,
    assess_correspondence,
    correspondence_strength,
    decide_date,
    decide_source,
    search_adequate,
)

T = get_settings().classification


def m(v: float | None) -> Metric:
    return Metric(MetricState.COMPUTED, v) if v is not None else Metric()


@pytest.mark.parametrize("sim,title_kw,passage_kw,level", [
    (0.90, None, None, "STRONG"),       # near-identical title on its own
    (0.74, 0.57, None, "STRONG"),       # altered headline whose keywords are in the title
    (0.60, None, 0.70, "PLAUSIBLE"),    # keyword support from the passages
    (0.78, 0.20, 0.30, "NONE"),         # similar topic alone is not correspondence
    (None, 0.80, None, "PLAUSIBLE"),    # no similarity model: strong title coverage
    (None, 0.40, None, "NONE"),
    (None, None, None, "UNKNOWN"),
])
def test_correspondence_levels(sim, title_kw, passage_kw, level):
    assert assess_correspondence(CorrespondenceInputs(m(sim), m(title_kw), m(passage_kw)), T).level == level


@pytest.mark.parametrize("kwargs,status", [
    (dict(has_evidence=False, search_adequate=True, retrieval_failed=False, correspondence=None), SourceStatus.NOT_FOUND),
    (dict(has_evidence=False, search_adequate=False, retrieval_failed=False, correspondence=None), SourceStatus.INCOMPLETE),
    (dict(has_evidence=False, search_adequate=True, retrieval_failed=True, correspondence=None), SourceStatus.INCOMPLETE),
    (dict(has_evidence=False, search_adequate=True, retrieval_failed=False, correspondence=None,
          blocked_match="kalerkantho.com"), SourceStatus.INCOMPLETE),
    (dict(has_evidence=True, search_adequate=True, retrieval_failed=False,
          correspondence=Correspondence("PLAUSIBLE", ["b"])), SourceStatus.CONFIRMED),
    (dict(has_evidence=True, search_adequate=True, retrieval_failed=False,
          correspondence=Correspondence("PLAUSIBLE", ["b"]), blocked_match="kalerkantho.com"), SourceStatus.INCOMPLETE),
    (dict(has_evidence=True, search_adequate=True, retrieval_failed=False,
          correspondence=Correspondence("UNKNOWN", ["b"])), SourceStatus.INCOMPLETE),
    (dict(has_evidence=True, search_adequate=True, retrieval_failed=False,
          correspondence=Correspondence("NONE", ["b"])), SourceStatus.NOT_FOUND),
    (dict(has_evidence=True, search_adequate=False, retrieval_failed=False,
          correspondence=Correspondence("NONE", ["b"])), SourceStatus.INCOMPLETE),
])
def test_source_decision(kwargs, status):
    decided, basis = decide_source(**kwargs)
    assert decided == status and basis
    if kwargs.get("blocked_match"):
        assert "blocked automated access" in basis[-1]


def test_date_decision_only_applies_to_a_confirmed_source_with_a_claimed_date():
    d = date(2026, 6, 7)
    assert decide_date(None, d, source_confirmed=True) is None
    assert decide_date(d, d, source_confirmed=False) is None
    assert decide_date(d, None, source_confirmed=True) == DateStatus.INCOMPLETE
    assert decide_date(d, d, source_confirmed=True) == DateStatus.MATCHED
    assert decide_date(d, date(2026, 6, 8), source_confirmed=True) == DateStatus.MISMATCHED


def test_search_adequacy_and_strength():
    assert search_adequate(4, 2, min_calls=2, min_ratio=0.5)
    assert not search_adequate(4, 1, min_calls=2, min_ratio=0.5)
    assert not search_adequate(10, 4, min_calls=2, min_ratio=0.5)
    assert not search_adequate(0, 0, min_calls=0, min_ratio=0.0)
    assert correspondence_strength([0.5, None, 1.0]) == 0.75 and correspondence_strength([None]) == 0.0
