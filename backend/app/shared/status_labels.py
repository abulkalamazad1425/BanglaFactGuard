"""User-facing labels for stored verification statuses.

Stored enum values are unchanged (CONFIRMED / NOT_FOUND, MATCHED /
MISMATCHED, FAKE / NON_FAKE, ...); this is the single backend mapping to the
words users see. The website (`frontend/src/app/shared/utils/status-labels.ts`)
and the extension (`extension/src/shared.js`) carry the same table.

Source status answers one question: was a relevant article found in the
outlet the claim names? "Found" never means the claim is true, and "Not
Found" never means it is false.
"""

from __future__ import annotations

from app.core.constants import (
    DateStatus,
    HeadlineAlterationStatus,
    MultimodalPredictionLabel,
    OverallVerdict,
    SourceStatus,
)

SOURCE_QUESTION = "Relevant article from claimed source"

SOURCE_LABELS: dict[SourceStatus, str] = {
    SourceStatus.CONFIRMED: "Found",
    SourceStatus.NOT_FOUND: "Not Found",
    SourceStatus.INCOMPLETE: "Check incomplete",
}

NOT_FOUND_IN_CLAIMED_SOURCE = "Not found in claimed source"

HEADLINE_LABELS: dict[HeadlineAlterationStatus, str] = {
    HeadlineAlterationStatus.EXACT_MATCHED: "Exact Matched",
    HeadlineAlterationStatus.MEANING_PRESERVED: "Meaning Preserved",
    HeadlineAlterationStatus.ALTERED: "Altered",
}

DATE_LABELS: dict[DateStatus, str] = {
    DateStatus.MATCHED: "Matched",
    DateStatus.MISMATCHED: "Mismatched",
    DateStatus.INCOMPLETE: "Could not be determined",
}

AI_DECISION_LABELS: dict[MultimodalPredictionLabel, str] = {
    MultimodalPredictionLabel.FAKE: "Likely Fake",
    MultimodalPredictionLabel.NON_FAKE: "Likely Real",
}

OVERALL_LABELS: dict[OverallVerdict, str] = {
    OverallVerdict.REAL: "Real",
    OverallVerdict.FAKE: "Fake",
    OverallVerdict.MISLEADING: "Misleading",
    OverallVerdict.ALTERED: "Altered",
}


def ai_decision_label(prediction: MultimodalPredictionLabel | str | None) -> str | None:
    """`fake` -> Likely Fake; `non-fake` (or any non-fake class) -> Likely Real.
    This is the model's preliminary call, never an expert verdict."""
    if prediction is None:
        return None
    value = getattr(prediction, "value", prediction)
    return AI_DECISION_LABELS[
        MultimodalPredictionLabel.FAKE
        if str(value).upper() == MultimodalPredictionLabel.FAKE.value
        else MultimodalPredictionLabel.NON_FAKE
    ]
