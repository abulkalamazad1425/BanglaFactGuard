// ============================================================
// Result presentation rules — pure functions shared by the detail page,
// photo-card page, expert view and history, so a status badge, its reasoning
// and its checklist can never disagree.
//
// Rules enforced here (and unit-tested in result-view.spec.ts):
//  * A green check means a COMPLETED PASSING check. NOT_EVALUATED / unavailable
//    are neutral "not evaluated" rows, never greens. Historical rows with no
//    recorded check states render as "not recorded", not as passes.
//  * NOT_APPLICABLE checks are omitted (no "passed body-authenticity check"
//    on a photo card).
//  * A null score is "not applicable" / "unavailable" - never 0% or 100%.
//  * Body metrics exist only for claims that carried a submitted body.
// ============================================================

import {
  AnalysisDetails,
  CheckState,
  ClaimScope,
  DiscrepancyDetail,
  ManipulationFlags,
  MetricState,
  VerificationScores,
} from '../../models/verification.model';

export interface CheckRow {
  key: string;
  title: string;
  state: CheckState | 'NOT_RECORDED';
  icon: '✓' | '✗' | '—';
  cls: 'passed' | 'failed' | 'unknown';
  desc: string;
  discrepancies: DiscrepancyDetail[];
}

export interface ScoreRow {
  key: string;
  label: string;
  hint: string;
  value: number | null;
  /** "87.5%" or "Not applicable" / "Unavailable" - never a fabricated number. */
  display: string;
  state: MetricState | 'MISSING';
  note?: string;
  color: string;
}

export function hasBody(scope: ClaimScope | null | undefined): boolean {
  return scope === 'HEADLINE_WITH_BODY';
}

export function formatPercent(v: number | null | undefined, digits = 1): string {
  return v == null ? '—' : `${(v * 100).toFixed(digits)}%`;
}

const CHECK_META: Record<string, { title: string; pass: string; fail: string }> = {
  headline: {
    title: 'Headline vs source report',
    pass: 'No concrete difference found between the submitted headline and the source report.',
    fail: 'The submitted headline differs from the source report.',
  },
  body: {
    title: 'Submitted body vs source report',
    pass: 'No concrete difference found between the submitted body and the source report.',
    fail: 'The submitted body differs from the source report.',
  },
  numbers: {
    title: 'Numbers and units',
    pass: 'Claimed numbers match the source report.',
    fail: 'A claimed number differs from the source report.',
  },
  negation: {
    title: 'Negation',
    pass: 'The claim and the source agree on what is affirmed or denied.',
    fail: 'The claim affirms what the source denies (or the reverse).',
  },
  entities: {
    title: 'People, places and organisations (roles)',
    pass: 'No substituted or swapped entity found.',
    fail: 'An entity was substituted or its role swapped.',
  },
  scope: {
    title: 'Scope and quantifiers',
    pass: 'Quantifiers (all / some / at least / at most) agree with the source.',
    fail: 'A scope or quantifier differs from the source.',
  },
  attribution: {
    title: 'Attribution',
    pass: 'The statement is attributed to the same speaker as in the source.',
    fail: 'The statement is attributed to a different speaker than in the source.',
  },
  modality: {
    title: 'Plans vs completed events',
    pass: 'The claim and the source agree on whether this happened or is only planned/possible.',
    fail: 'The claim and the source disagree on whether this happened or is only planned/possible.',
  },
};

const CHECK_ORDER = ['headline', 'body', 'numbers', 'negation', 'entities', 'scope', 'attribution', 'modality'];

function discrepanciesFor(flags: ManipulationFlags, key: string): DiscrepancyDetail[] {
  const all = flags.discrepancies ?? [];
  switch (key) {
    case 'headline':
      return all.filter((d) => d.part === 'headline');
    case 'body':
      return all.filter((d) => d.part === 'body');
    case 'numbers':
      return all.filter((d) => d.kind === 'numbers');
    case 'negation':
      return all.filter((d) => d.kind === 'negation');
    case 'entities':
      return all.filter((d) => d.kind === 'entity_substitution' || d.kind === 'entity_role');
    case 'scope':
      return all.filter((d) => d.kind === 'scope');
    case 'attribution':
      return all.filter((d) => d.kind === 'attribution');
    case 'modality':
      return all.filter((d) => d.kind === 'modality');
    default:
      return [];
  }
}

export function buildCheckRows(
  flags: ManipulationFlags | null | undefined,
  scope: ClaimScope | null | undefined,
): CheckRow[] {
  const f = flags ?? {};
  const states = f.check_states ?? {};

  // Historical result: no check states were recorded. Never infer passes from
  // default-false booleans - show what was flagged and say the rest was not recorded.
  if (Object.keys(states).length === 0) {
    const rows: CheckRow[] = [];
    const legacy: Array<[boolean | undefined, string, string]> = [
      [f.headline_manipulated, 'headline', CHECK_META['headline'].fail],
      [f.body_altered, 'body', CHECK_META['body'].fail],
      [f.numbers_altered, 'numbers', CHECK_META['numbers'].fail],
      [f.entities_replaced, 'entities', CHECK_META['entities'].fail],
    ];
    for (const [flag, key, fail] of legacy) {
      if (flag && (key !== 'body' || hasBody(scope))) {
        rows.push({
          key,
          title: CHECK_META[key].title,
          state: 'FAILED',
          icon: '✗',
          cls: 'failed',
          desc: fail,
          discrepancies: discrepanciesFor(f, key),
        });
      }
    }
    rows.push({
      key: 'not-recorded',
      title: 'Detailed alteration checks',
      state: 'NOT_RECORDED',
      icon: '—',
      cls: 'unknown',
      desc: 'Detailed check results were not recorded for this older result, so no check is shown as passed.',
      discrepancies: [],
    });
    return rows;
  }

  const rows: CheckRow[] = [];
  for (const key of CHECK_ORDER) {
    const state = states[key];
    if (state === undefined || state === 'NOT_APPLICABLE') continue;
    if (key === 'body' && !hasBody(scope)) continue; // photo cards / headline-only: never shown
    const meta = CHECK_META[key];
    if (state === 'PASSED') {
      rows.push({ key, title: meta.title, state, icon: '✓', cls: 'passed', desc: meta.pass, discrepancies: [] });
    } else if (state === 'FAILED') {
      rows.push({
        key,
        title: meta.title,
        state,
        icon: '✗',
        cls: 'failed',
        desc: meta.fail,
        discrepancies: discrepanciesFor(f, key),
      });
    } else {
      rows.push({
        key,
        title: meta.title,
        state,
        icon: '—',
        cls: 'unknown',
        desc: 'Not evaluated — the information needed to run this check was not available.',
        discrepancies: [],
      });
    }
  }
  return rows;
}

const COLORS = {
  blue: '#3b82f6',
  purple: '#8b5cf6',
  indigo: '#6366f1',
  cyan: '#06b6d4',
  pink: '#ec4899',
};

interface RowSpec {
  key: keyof VerificationScores;
  metricKey: string;
  label: string;
  hint: string;
  color: string;
  bodyOnly?: boolean;
}

const SCORE_SPECS: RowSpec[] = [
  { key: 'headline_similarity', metricKey: 'headline_similarity', label: 'Headline similarity to source title',
    hint: 'Embedding similarity between the submitted headline and the source report\'s title. A measurement, not a probability of truth.', color: COLORS.blue },
  { key: 'passage_similarity', metricKey: 'passage_similarity', label: 'Support in relevant source passages',
    hint: 'Similarity to the sentences of the source article that discuss this claim (with surrounding context). Supporting evidence, not a body match.', color: COLORS.blue },
  { key: 'headline_keyword_coverage', metricKey: 'headline_keyword_coverage', label: 'Headline keywords found in source title',
    hint: 'Share of the claim\'s keywords (weighted) that occur in the source title.', color: COLORS.indigo },
  { key: 'passage_keyword_coverage', metricKey: 'passage_keyword_coverage', label: 'Claim keywords found in source passages',
    hint: 'Share of the claim\'s keywords that occur in the source title and relevant passages.', color: COLORS.indigo },
  { key: 'entity_match', metricKey: 'entity_match', label: 'Claimed entities found in source',
    hint: 'Share of people/places/organisations named in the claim that the source evidence also names. Extra entities in the source are not penalised.', color: COLORS.purple },
  { key: 'numerical_consistency', metricKey: 'numerical_consistency', label: 'Claimed numbers supported by source',
    hint: 'Share of numbers in the claim that appear (same value and unit) in the source evidence.', color: COLORS.cyan },
  { key: 'body_similarity', metricKey: 'body_similarity', label: 'Submitted body vs source body',
    hint: 'Submitted body compared passage-by-passage with the source article. Only exists when a body was submitted.', color: COLORS.blue, bodyOnly: true },
  { key: 'body_keyword_coverage', metricKey: 'body_keyword_coverage', label: 'Submitted-body keywords found in source',
    hint: 'Share of keywords of the submitted body that occur in the source article.', color: COLORS.indigo, bodyOnly: true },
  { key: 'contradiction_score', metricKey: 'contradiction', label: 'Possible-contradiction signal (NLI)',
    hint: 'NLI contradiction probability. The NLI model has not been validated on Bangla: a high value is a prompt for review, not a finding.', color: COLORS.pink },
];

export function buildScoreRows(
  scores: VerificationScores | null | undefined,
  analysis: AnalysisDetails | null | undefined,
  scope: ClaimScope | null | undefined,
): ScoreRow[] {
  const s = scores ?? {};
  const rows: ScoreRow[] = [];
  for (const spec of SCORE_SPECS) {
    if (spec.bodyOnly && !hasBody(scope)) continue; // no Body Match for headline-only / photo cards
    const raw = s[spec.key] as number | null | undefined;
    const metric = analysis?.metrics?.[spec.metricKey];
    if (raw != null) {
      rows.push({ key: spec.key, label: spec.label, hint: spec.hint, value: raw,
        display: formatPercent(raw), state: 'COMPUTED', color: spec.color });
      continue;
    }
    // null: say why. Rows nobody could ever compute (no metric info, not a core row) are skipped.
    if (metric) {
      if (metric.state === 'NOT_APPLICABLE' && spec.key !== 'entity_match' && spec.key !== 'numerical_consistency') continue;
      rows.push({
        key: spec.key, label: spec.label, hint: spec.hint, value: null,
        display: metric.state === 'NOT_APPLICABLE' ? 'Not applicable'
          : metric.state === 'EMPTY' ? 'No comparable keywords' : 'Unavailable',
        state: metric.state, note: metric.reason ?? undefined, color: spec.color,
      });
    } else if (spec.key === 'headline_similarity') {
      rows.push({ key: spec.key, label: spec.label, hint: spec.hint, value: null,
        display: 'Not recorded', state: 'MISSING', color: spec.color });
    }
  }
  return rows;
}

/** Wording for the single "strength" number. It is NOT a probability of truth. */
export const STRENGTH_LABEL = 'Check strength';
export const STRENGTH_HELP =
  'Mean of the similarity / coverage measurements behind this automated result. ' +
  'It summarises how much evidence was measured — it is not the probability that the claim is true.';

export function strengthFor(confidence: number | null | undefined, sourceStatus?: string | null): string {
  if (sourceStatus === 'INCOMPLETE') return '—';
  return confidence == null ? '—' : `${(confidence * 100).toFixed(0)}%`;
}
