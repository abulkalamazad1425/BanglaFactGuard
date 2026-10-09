"""Display split of a MATCHED headline into Exact Matched / Meaning Preserved,
from stored evidence only. ALTERED passes through untouched."""

from types import SimpleNamespace

import pytest

from app.core.constants import ContentStatus
from app.core.constants import HeadlineAlterationStatus as H
from app.features.verification.headline_status import (
    derive_headline_status,
    headline_status_for_result,
)

M = ContentStatus.MATCHED


@pytest.mark.parametrize("status,kwargs,expected", [
    (ContentStatus.ALTERED, dict(exact_match=True), H.ALTERED),
    (M, dict(exact_match=True), H.EXACT_MATCHED),
    (M, dict(basis="exact"), H.EXACT_MATCHED),
    (M, dict(exact_match=False, claim_headline="ক খ", source_title="ক খ"), H.MEANING_PRESERVED),  # stored flag wins
    (M, dict(claim_headline="ঢাকায়  বৃষ্টি।", source_title="ঢাকায় বৃষ্টি"), H.EXACT_MATCHED),     # legacy re-check
    (M, dict(claim_headline="ঢাকায় বৃষ্টি", source_title="ঢাকায়, বৃষ্টি"), H.MEANING_PRESERVED),
    (M, dict(basis="semantic_equivalence"), H.MEANING_PRESERVED),
    (M, {}, H.MEANING_PRESERVED),                                                                  # no evidence
    ("MATCHED", dict(exact_match=True), H.EXACT_MATCHED),
    (None, {}, None),
])
def test_derived_status(status, kwargs, expected):
    assert derive_headline_status(status, **kwargs) == expected


def test_a_stored_result_uses_its_saved_detail_and_legacy_rows_have_none():
    row = SimpleNamespace(
        headline_check_status="COMPLETED", content_status=M, headline_exact_match=None,
        analysis_details={"headline_alteration": {"status": "COMPLETED", "reason": "r", "basis": "exact", "claim_headline": "h"}},
    )
    assert headline_status_for_result(row) == H.EXACT_MATCHED
    row.headline_check_status = None
    assert headline_status_for_result(row) is None and headline_status_for_result(None) is None
