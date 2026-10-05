// ============================================================
// Result presentation rules — pure functions shared by the detail page,
// photo-card page, expert view and history, so a finding, its explanation
// and its evidence can never disagree.
//
// Rules enforced here (and unit-tested in result-view.spec.ts):
//  * Headline Alteration has exactly two verdicts (matched / altered). When
//    none was reached, the reason is shown — never a guessed verdict.
//  * A legacy result's old content verdict is never shown as a headline verdict.
//  * Body similarity scores are measurements only, shown apart from the
//    headline verdict. An unavailable score is "Unavailable" with its reason,
//    never 0 or 0%.
// ============================================================

import {
  AnalysisDetails,
  BodySimilarityMetric,
  BodySimilarityReport,
  ClaimScope,
  HeadlineCheckStatus,
  VerificationResponse,
} from '../../models/verification.model';

export function hasBody(scope: ClaimScope | null | undefined): boolean {
  return scope === 'HEADLINE_WITH_BODY';
}

export function formatPercent(v: number | null | undefined, digits = 0): string {
  return v == null ? '—' : `${(v * 100).toFixed(digits)}%`;
}

// ── Headline Alteration ──────────────────────────────────────────────────

export type HeadlineTone = 'matched' | 'altered' | 'none';

export interface HeadlineView {
  tone: HeadlineTone;
  title: string;
  summary: string;
}

export const HEADLINE_STATUS_TEXT: Record<HeadlineCheckStatus, { title: string; summary: string }> = {
  COMPLETED: { title: 'Compared', summary: '' },
  SOURCE_NOT_FOUND: {
    title: 'Not compared',
    summary: 'No corresponding report was found in the selected outlet, so there is no title to compare with.',
  },
  SOURCE_CHECK_INCOMPLETE: {
    title: 'Not compared',
    summary: 'The source search could not be completed, so the headline was not compared. This is not a finding about the headline.',
  },
  SOURCE_TITLE_MISSING: {
    title: 'No verdict',
    summary: 'The source report has no readable title, so the headline could not be compared.',
  },
  MODEL_UNAVAILABLE: {
    title: 'No verdict',
    summary: 'The meaning comparison was unavailable, so no verdict was reached. This does not mean the headline was altered.',
  },
  UNDETERMINED: {
    title: 'No verdict',
    summary: 'Neither the same meaning nor a meaningful difference could be established, so no verdict was reached.',
  },
};

/** The headline finding for the summary card. The AI verdict is replaced by
 *  the expert's when finalized (`content_status` already carries that). */
export function headlineView(r: VerificationResponse): HeadlineView {
  if (r.content_status === 'MATCHED') {
    return { tone: 'matched', title: 'Headline matched', summary: 'The claim headline has the same meaning as the source title.' };
  }
  if (r.content_status === 'ALTERED') {
    return { tone: 'altered', title: 'Headline altered', summary: 'The claim headline differs meaningfully from the source title. See the evidence below.' };
  }
  if (r.legacy_result) {
    return {
      tone: 'none',
      title: 'Not available',
      summary: 'This result was recorded by an earlier version of the checker; it has no Headline Alteration verdict.',
    };
  }
  const status: HeadlineCheckStatus =
    r.headline_check_status ??
    (r.source_status === 'NOT_FOUND' ? 'SOURCE_NOT_FOUND' : 'SOURCE_CHECK_INCOMPLETE');
  return { tone: 'none', ...HEADLINE_STATUS_TEXT[status] };
}

export const DIFFERENCE_LABELS: Record<string, string> = {
  numbers: 'Number changed',
  date: 'Date changed',
  negation: 'Negation reversed',
  modality: 'Planned vs. completed',
  scope: 'Quantifier changed',
  subject_object: 'Roles reversed (who did what to whom)',
  attribution: 'Attribution changed',
  denial: 'Denial removed',
  entity: 'Person, place or organisation changed',
  main_point: 'Main statement differs',
};

export function differenceLabel(kind: string): string {
  return DIFFERENCE_LABELS[kind] ?? 'Meaningful difference';
}

// ── Body similarity (measurements only — never a verdict) ───────────────

export type BodyMetricKey = 'tfidf_cosine' | 'jaccard' | 'normalized_levenshtein' | 'semantic_cosine';

export interface BodyMetricSpec {
  key: BodyMetricKey;
  label: string;
  measures: string;
  range: string;
}

export const BODY_METRICS: BodyMetricSpec[] = [
  {
    key: 'tfidf_cosine',
    label: 'TF-IDF cosine similarity',
    measures: 'How much the two texts share their important words, giving distinctive words more weight than common ones.',
    range: '0 = no important words in common · 1 = the same words in the same proportions',
  },
  {
    key: 'jaccard',
    label: 'Jaccard similarity',
    measures: 'The share of unique words used by both texts: words in common ÷ all distinct words.',
    range: '0 = no word in common · 1 = exactly the same vocabulary',
  },
  {
    key: 'normalized_levenshtein',
    label: 'Normalized Levenshtein similarity',
    measures: 'How few character edits turn one text into the other: 1 − edits ÷ length of the longer text. Low when one text is much longer.',
    range: '0 = entirely different characters · 1 = identical text',
  },
  {
    key: 'semantic_cosine',
    label: 'Semantic similarity (LaBSE embedding cosine)',
    measures: 'Meaning-based closeness from a multilingual sentence-embedding model, so reworded text can still score high. Long texts are compared passage by passage.',
    range: '0 = unrelated meaning · 1 = the same meaning (negative raw values are shown as 0)',
  },
];

export type ScoreBand = 'High' | 'Moderate' | 'Low';

/** A descriptive band for a 0–1 similarity score. It describes overlap only. */
export function scoreBand(value: number): ScoreBand {
  if (value >= 0.75) return 'High';
  if (value >= 0.4) return 'Moderate';
  return 'Low';
}

export interface BodyMetricRow extends BodyMetricSpec {
  available: boolean;
  /** 0–1, or null when unavailable. */
  value: number | null;
  /** "82%" or "Unavailable" — never a fabricated number. */
  display: string;
  band: ScoreBand | null;
  note: string | null;
}

export function buildBodyMetricRows(report: BodySimilarityReport | null | undefined): BodyMetricRow[] {
  if (!report || report.status === 'SKIPPED') return [];
  return BODY_METRICS.map((spec) => {
    const m: BodySimilarityMetric | null | undefined = report[spec.key];
    const value = m?.available && m.value != null ? m.value : null;
    return {
      ...spec,
      available: value !== null,
      value,
      display: value === null ? 'Unavailable' : formatPercent(value),
      band: value === null ? null : scoreBand(value),
      note: value === null ? (m?.reason ?? report.reason ?? 'This score could not be computed.') : bodyMetricNote(spec.key, m),
    };
  });
}

function bodyMetricNote(key: BodyMetricKey, m: BodySimilarityMetric | null | undefined): string | null {
  const d = m?.details ?? {};
  if (key === 'normalized_levenshtein' && d['truncated']) {
    return `Compared on the first ${d['claim_chars_compared']} / ${d['source_chars_compared']} characters of very long texts.`;
  }
  if (key === 'semantic_cosine' && (d['claim_truncated'] || d['source_truncated'])) {
    return 'Very long text: only the first passages were compared.';
  }
  return null;
}

/** Why the body section has no scores, or null when it does. */
export function bodySectionMessage(report: BodySimilarityReport | null | undefined, scope: ClaimScope | null | undefined): string | null {
  if (!hasBody(scope)) return null;
  if (!report) return 'Body similarity was not recorded for this result.';
  if (report.status === 'COMPUTED') return null;
  return report.reason ?? 'Body similarity is unavailable for this result.';
}

// ── Source correspondence measurements (reviewer detail) ────────────────

export interface MeasurementRow {
  key: string;
  label: string;
  value: number | null;
  display: string;
  note: string | null;
}

const CORRESPONDENCE_SPECS: Array<{ key: string; label: string }> = [
  { key: 'headline_title_similarity', label: 'Headline / source title similarity' },
  { key: 'title_keyword_coverage', label: 'Claim keywords found in the source title' },
  { key: 'passage_keyword_coverage', label: 'Claim keywords found in the source title and passages' },
];

export function buildCorrespondenceRows(analysis: AnalysisDetails | null | undefined): MeasurementRow[] {
  const metrics = analysis?.metrics ?? {};
  return CORRESPONDENCE_SPECS.filter((s) => metrics[s.key]).map((s) => {
    const m = metrics[s.key];
    const value = m.state === 'COMPUTED' && m.value != null ? m.value : null;
    return {
      key: s.key,
      label: s.label,
      value,
      display: value === null ? 'Unavailable' : formatPercent(value),
      note: value === null ? (m.reason ?? null) : null,
    };
  });
}
