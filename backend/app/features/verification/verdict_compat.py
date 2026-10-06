"""Display helper for the expert queue's "AI said" column.

History: this module used to also hold ``derive_expert_verdict``, which
projected the automated (source, content) result onto the legacy single-
category TRUE / FALSE / PARTIALLY_TRUE / NOT_FOUND_IN_CLAIMED_SOURCE enum so
the automated system could cast a vote of its own in the expert-consensus
mechanism (stored as ``verification_results.ai_consensus_label``). That
projection was removed on purpose:

* The automated system verifies Source, Content and Date ONLY. Fake / Real /
  Misleading / Altered is an exclusively expert-finalized assessment, so the
  automation must not derive or store any overall truth label — least of all
  by collapsing INCOMPLETE or NOT_FOUND states into TRUE/FALSE/PARTIALLY_TRUE.
* Nothing in expert review, credibility scoring or escalation ever read
  ``ai_consensus_label`` (they use the structured source/content/date values
  and the experts' own votes), so removing the writer changes no review,
  locking, audit, credibility or escalation behaviour.

The column remains in the database (historical rows are preserved, not
erased) but is no longer written.
"""

from __future__ import annotations

from app.core.constants import DateStatus, HeadlineAlterationStatus, SourceStatus
from app.shared.status_labels import (
    DATE_LABELS,
    HEADLINE_LABELS,
    NOT_FOUND_IN_CLAIMED_SOURCE,
    SOURCE_LABELS,
    SOURCE_QUESTION,
)


def format_verdict_display(
    source_status: SourceStatus | None,
    headline_status: HeadlineAlterationStatus | None,
    date_status: DateStatus | None = None,
) -> str | None:
    """Human-readable one-line summary for the expert queue's "AI said" column."""
    if source_status is None:
        return None
    if source_status == SourceStatus.NOT_FOUND:
        return NOT_FOUND_IN_CLAIMED_SOURCE
    if source_status == SourceStatus.INCOMPLETE:
        return f"{SOURCE_QUESTION}: {SOURCE_LABELS[source_status]}"

    parts = [f"{SOURCE_QUESTION}: {SOURCE_LABELS[source_status]}"]
    parts.append(f"Headline: {HEADLINE_LABELS[headline_status]}" if headline_status is not None else "Headline: No verdict")
    if date_status is not None:
        parts.append(f"Date: {DATE_LABELS[date_status]}")
    return " · ".join(parts)
