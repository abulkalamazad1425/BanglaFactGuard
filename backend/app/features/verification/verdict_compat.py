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
