"""Who may read a submission that has no published result yet.

Completed results (in expert review, finalized, escalated) follow the existing
public visibility policy (Fact Explorer already lists them). A submission that
is still PENDING/PROCESSING, or FAILED, is the submitter's private working
state — its image and extracted text are not public — so only the owner (and
staff) may read it. Anonymous submissions (no owner) stay reachable by their
unguessable id, matching existing anonymous behaviour; they are not promised
an account-owned history.
"""

from __future__ import annotations

from app.core.constants import SubmissionStatus
from app.features.submissions.models import Submission

_PUBLIC_STATUSES = (
    SubmissionStatus.EXPERT_REVIEW,
    SubmissionStatus.FINALIZED,
    SubmissionStatus.ESCALATED,
)


def viewer_can_see(submission: Submission, user) -> bool:
    if submission.status in _PUBLIC_STATUSES:
        return True
    if submission.submitter_id is None:
        return True
    if user is None:
        return False
    return user.id == submission.submitter_id or getattr(user, "role", None) in ("admin", "expert")
