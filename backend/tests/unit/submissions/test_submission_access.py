"""Unpublished (pending/failed) submissions are private to their owner and staff."""

import uuid
from types import SimpleNamespace

import pytest

from app.core.constants import SubmissionStatus
from app.features.submissions.access import viewer_can_see

OWNER = SimpleNamespace(id=uuid.uuid4(), role="user")
OTHER = SimpleNamespace(id=uuid.uuid4(), role="user")
EXPERT = SimpleNamespace(id=uuid.uuid4(), role="expert")


@pytest.mark.parametrize("status", [SubmissionStatus.PENDING, SubmissionStatus.PROCESSING, SubmissionStatus.FAILED])
def test_unpublished_work_is_private(status):
    owned = SimpleNamespace(status=status, submitter_id=OWNER.id)
    assert viewer_can_see(owned, OWNER) and viewer_can_see(owned, EXPERT)
    assert not viewer_can_see(owned, OTHER) and not viewer_can_see(owned, None)
    assert viewer_can_see(SimpleNamespace(status=status, submitter_id=None), None)  # anonymous: id-only access


@pytest.mark.parametrize("status", [SubmissionStatus.EXPERT_REVIEW, SubmissionStatus.FINALIZED, SubmissionStatus.ESCALATED])
def test_published_results_are_public(status):
    assert viewer_can_see(SimpleNamespace(status=status, submitter_id=OWNER.id), None)
