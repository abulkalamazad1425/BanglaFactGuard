import pytest

from app.core.constants import DateStatus, HeadlineAlterationStatus, SourceStatus
from app.features.verification.verdict_compat import format_verdict_display


@pytest.mark.parametrize("source,headline,date_,expected", [
    (None, None, None, None),
    (SourceStatus.NOT_FOUND, None, DateStatus.MATCHED, "Not found in claimed source"),
    (SourceStatus.INCOMPLETE, None, None, "Relevant article from claimed source: Check incomplete"),
    (SourceStatus.CONFIRMED, HeadlineAlterationStatus.ALTERED, None,
     "Relevant article from claimed source: Found · Headline: Altered"),
    (SourceStatus.CONFIRMED, None, DateStatus.MISMATCHED,
     "Relevant article from claimed source: Found · Headline: No verdict · Date: Mismatched"),
])
def test_ai_said_column_never_states_an_overall_verdict(source, headline, date_, expected):
    assert format_verdict_display(source, headline, date_) == expected
