// ============================================================
// One table of user-facing status words, shared by every page.
// Mirrors backend app/shared/status_labels.py and extension/src/shared.js —
// stored API values (CONFIRMED, MISMATCHED, FAKE, …) never change.
//
// Display rules (unit-tested in status-labels.spec.ts):
//  * "Relevant article from claimed source" is Found / Not Found. Found is
//    shown only on the detailed result page; summaries, cards and the
//    extension show only "Not found in claimed source" (and then no headline,
//    date or body findings).
//  * Headline: Exact Matched / Meaning Preserved / Altered.
//  * Date: Matched / Mismatched — only when the submitter claimed a date.
//  * AI decision (text & image model): Likely Fake / Likely Real — never the
//    expert final verdict.
// ============================================================

import {
  DateStatus,
  HeadlineAlterationStatus,
  OverallVerdict,
  SourceStatus,
} from '../../models/verification.model';

export const SOURCE_QUESTION = 'Relevant article from claimed source';
export const NOT_FOUND_IN_CLAIMED_SOURCE = 'Not found in claimed source';

export const VERIFIED_SOURCES_QUESTION = 'Relevant articles from verified sources';
export const NOT_FOUND_IN_VERIFIED_SOURCES =
  'No matching report was found in the verified sources searched';

export const VERIFIED_SOURCE_EXPLANATIONS: Record<SourceStatus, string> = {
  CONFIRMED:
    'Related reports found in verified sources. This alone does not make the claim true, and it ' +
    'does not show which outlet originally published it.',
  NOT_FOUND:
    'No matching report was found in the verified sources searched. This alone does not prove ' +
    'the news is false.',
  INCOMPLETE:
    'Verification could not be completed. No conclusion can be drawn about whether a verified ' +
    'source carried this report.',
};

/** Why a claim was checked against the verified sources instead of one outlet. */
export const SOURCE_RESOLUTION_NOTES: Record<string, string> = {
  SOURCE_NOT_SUPPLIED:
    'No claimed outlet was selected, so the active verified news sources were searched.',
  SOURCE_NOT_DETECTED:
    'No news outlet could be identified on the photo card, so the active verified news sources were searched.',
  SOURCE_UNRECOGNIZED:
    'The named outlet is not one of the verified sources, so the active verified news sources were searched instead.',
  SOURCE_INACTIVE:
    'The named outlet is not currently an active verified source, so the active verified news sources were searched instead.',
};

export const SOURCE_LABELS: Record<SourceStatus, string> = {
  CONFIRMED: 'Found',
  NOT_FOUND: 'Not Found',
  INCOMPLETE: 'Check incomplete',
};

export const SOURCE_EXPLANATIONS: Record<SourceStatus, string> = {
  CONFIRMED:
    'A relevant article was found in the news outlet the claim names. This alone does not make the claim true.',
  NOT_FOUND:
    'No relevant article was found in the news outlet the claim names. This alone does not prove the news is false.',
  INCOMPLETE:
    'The search of the claimed outlet could not be completed. No conclusion ' +
    'can be drawn about whether it published this report; try a new check ' +
    'later.',
};

export const HEADLINE_LABELS: Record<HeadlineAlterationStatus, string> = {
  EXACT_MATCHED: 'Exact Matched',
  MEANING_PRESERVED: 'Meaning Preserved',
  ALTERED: 'Altered',
};

export const HEADLINE_EXPLANATIONS: Record<HeadlineAlterationStatus, string> = {
  EXACT_MATCHED:
    'The claim headline is word-for-word the same as the source title (ignoring spacing and a final full stop).',
  MEANING_PRESERVED: 'The wording differs from the source title, but the meaning is the same.',
  ALTERED: 'The claim headline differs meaningfully from the source title. See the evidence below.',
};

export const DATE_LABELS: Record<DateStatus, string> = {
  MATCHED: 'Matched',
  MISMATCHED: 'Mismatched',
  INCOMPLETE: 'Could not be determined',
};

export const DATE_EXPLANATIONS: Record<DateStatus, string> = {
  MATCHED: 'The claimed publication date agrees with the source article’s date.',
  MISMATCHED:
    'The claimed publication date differs from the source article’s date. This alone does not mean the news is false.',
  INCOMPLETE: 'The source article’s own publication date could not be determined.',
};

export const OVERALL_LABELS: Record<OverallVerdict, string> = {
  REAL: 'Real',
  FAKE: 'Fake',
  MISLEADING: 'Misleading',
  ALTERED: 'Altered',
};

/** The text & image model's call: `FAKE` -> Likely Fake, any non-fake class -> Likely Real. */
export function aiDecisionLabel(prediction?: string | null): string | null {
  if (!prediction) return null;
  const value = prediction.toUpperCase();
  if (value === 'FAKE' || value === 'LIKELY FAKE') return 'Likely Fake';
  return 'Likely Real';
}

/** A short finding line for a card or summary (never "Found"). */
export interface FindingChip {
  label: string;
  value: string;
  tone: 'positive' | 'caution' | 'neutral';
}

export function preliminaryChips(f: {
  source_status?: SourceStatus | null;
  headline_status?: HeadlineAlterationStatus | null;
  date_status?: DateStatus | null;
  claimed_date?: string | null;
}): FindingChip[] {
  if (!f.source_status) return [];
  if (f.source_status === 'NOT_FOUND') {
    return [{ label: 'Source', value: NOT_FOUND_IN_CLAIMED_SOURCE, tone: 'neutral' }];
  }
  if (f.source_status === 'INCOMPLETE') {
    return [{ label: 'Source', value: 'Check incomplete', tone: 'neutral' }];
  }
  const chips: FindingChip[] = [];
  chips.push(
    f.headline_status
      ? {
          label: 'Headline',
          value: HEADLINE_LABELS[f.headline_status],
          tone: f.headline_status === 'ALTERED' ? 'caution' : 'positive',
        }
      : { label: 'Headline', value: 'No verdict', tone: 'neutral' },
  );
  if (f.claimed_date && f.date_status) {
    chips.push({
      label: 'Date',
      value: DATE_LABELS[f.date_status],
      tone:
        f.date_status === 'MATCHED'
          ? 'positive'
          : f.date_status === 'MISMATCHED'
            ? 'caution'
            : 'neutral',
    });
  }
  return chips;
}

/** What happens after a claim is accepted — told differently to a signed-in
 *  user (notified, listed in My Submissions) and an anonymous one (nothing is
 *  saved to an account, so the progress link is the way back). */
export function verificationFollowUp(
  signedIn: boolean,
  where: 'accepted' | 'progress-page' = 'accepted',
): string {
  const keep =
    where === 'progress-page' ? 'keep this page’s link' : 'keep the “View progress” link';
  return signedIn
    ? 'Verification may take a few minutes. You can continue browsing — you will be ' +
        'notified when the preliminary result is ready and again when experts reach a ' +
        'final verdict. Follow this claim in My Submissions; both results also appear in ' +
        'Fact Explorer.'
    : 'Verification may take a few minutes. You can continue browsing. You are not ' +
        'signed in, so this claim is not saved to an account and you will not be ' +
        `notified — ${keep} to come back to it. Preliminary and ` +
        'final results also appear in Fact Explorer. Sign in before submitting to have ' +
        'your claims listed in My Submissions.';
}
