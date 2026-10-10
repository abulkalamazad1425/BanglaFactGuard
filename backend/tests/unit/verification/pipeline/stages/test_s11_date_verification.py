"""S11: the claimed day vs the report's datePublished day, only for a
confirmed source; an unknown report date is INCOMPLETE, never MISMATCHED."""

from datetime import date

import pytest

from app.core.constants import DateStatus, SourceStatus
from app.features.verification.pipeline.stages.s11_date_verification import DateVerificationStage
from tests.helpers.pipeline import article, make_context

REPORT_DAY = date(2026, 6, 7)


@pytest.mark.parametrize("claimed,report,status,expected", [
    (REPORT_DAY, REPORT_DAY, SourceStatus.CONFIRMED, DateStatus.MATCHED),
    (date(2026, 1, 1), REPORT_DAY, SourceStatus.CONFIRMED, DateStatus.MISMATCHED),
    (REPORT_DAY, None, SourceStatus.CONFIRMED, DateStatus.INCOMPLETE),
    (None, REPORT_DAY, SourceStatus.CONFIRMED, None),
    (REPORT_DAY, REPORT_DAY, SourceStatus.NOT_FOUND, None),
])
async def test_date_status(claimed, report, status, expected):
    ctx = make_context("শিরোনাম", published_date=claimed, top=article("শিরোনাম", published=report))
    ctx.source_status = status
    out = await DateVerificationStage().execute(ctx)
    assert out.date_status == expected
    if status == SourceStatus.CONFIRMED:
        assert (out.analysis.date.claimed_date, out.analysis.date.article_date) == (claimed, report)
        assert out.analysis.date.provenance == ("json_ld.datePublished" if report else None)
    else:
        assert out.analysis.date is None
