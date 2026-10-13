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
