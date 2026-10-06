import { Component, Input } from '@angular/core';
import { NgClass } from '@angular/common';
import {
  ContentStatus,
  DateStatus,
  HeadlineAlterationStatus,
  OverallVerdict,
  SourceStatus,
} from '../../../models/verification.model';
import {
  DATE_LABELS,
  HEADLINE_LABELS,
  NOT_FOUND_IN_CLAIMED_SOURCE,
  OVERALL_LABELS,
  aiDecisionLabel,
} from '../../utils/status-labels';

type BadgeConfig = { text: string; cls: string; icon: string; title?: string };

const OVERALL_CONFIG: Record<OverallVerdict, BadgeConfig> = {
  REAL: { text: OVERALL_LABELS.REAL, cls: 'badge-true', icon: '✓' },
  FAKE: { text: OVERALL_LABELS.FAKE, cls: 'badge-false', icon: '✗' },
  MISLEADING: { text: OVERALL_LABELS.MISLEADING, cls: 'badge-partial', icon: '◑' },
  ALTERED: { text: OVERALL_LABELS.ALTERED, cls: 'badge-partial', icon: '✎' },
};

const HEADLINE_CONFIG: Record<HeadlineAlterationStatus, BadgeConfig> = {
  EXACT_MATCHED: { text: `Headline: ${HEADLINE_LABELS.EXACT_MATCHED}`, cls: 'badge-true', icon: '✓' },
  MEANING_PRESERVED: { text: `Headline: ${HEADLINE_LABELS.MEANING_PRESERVED}`, cls: 'badge-true', icon: '≈' },
  ALTERED: { text: `Headline: ${HEADLINE_LABELS.ALTERED}`, cls: 'badge-partial', icon: '◑' },
};

// Legacy callers that only have the stored MATCHED/ALTERED verdict.
const CONTENT_CONFIG: Record<ContentStatus, BadgeConfig> = {
  MATCHED: { text: 'Headline: Matched', cls: 'badge-true', icon: '✓' },
  ALTERED: { text: `Headline: ${HEADLINE_LABELS.ALTERED}`, cls: 'badge-partial', icon: '◑' },
};

const DATE_CONFIG: Record<DateStatus, BadgeConfig> = {
  MATCHED: { text: `Date: ${DATE_LABELS.MATCHED}`, cls: 'badge-true', icon: '✓' },
  MISMATCHED: { text: `Date: ${DATE_LABELS.MISMATCHED}`, cls: 'badge-partial', icon: '≠' },
  INCOMPLETE: { text: `Date: ${DATE_LABELS.INCOMPLETE}`, cls: 'badge-incomplete', icon: '?' },
};

/**
 * Verdict and finding chips. Every chip carries readable text (and an icon),
 * never colour alone.
 * - `[overallVerdict]` — the FINAL decision (Real/Fake/Misleading/Altered).
 * - `[label]` — the text & image model's preliminary call, shown as
 *   "AI: Likely Fake / Likely Real" — never as a final verdict.
 * - `[sourceStatus]` + `[headlineStatus]`/`[contentStatus]` + `[dateStatus]`
 *   — preliminary findings in summary form: "Found" is never shown here; a
 *   missing article shows only "Not found in claimed source". Set
 *   `[hideDate]` when the submitter claimed no date.
 */
@Component({
  selector: 'app-verdict-badge',
  standalone: true,
  imports: [NgClass],
  template: `
    @for (badge of badges; track badge.text) {
      <span class="badge" [ngClass]="badge.cls" [attr.title]="badge.title || null">
        @if (badge.icon) {<span class="badge-icon" aria-hidden="true">{{ badge.icon }}</span>}
        {{ badge.text }}
      </span>
    }
  `,
  host: { '[class.inline]': 'true' },
  styles: [`
    :host { display: inline-flex; gap: 6px; flex-wrap: wrap; }
    .badge { padding: 6px 11px; font-size: 13px; font-weight: 700; line-height: 1.4; border: 1px solid currentColor; border-radius: 6px; }
    .badge-icon { font-weight: 800; }
  `],
})
export class VerdictBadgeComponent {
  private _preliminary = false;
  @Input() set preliminary(value: boolean) { this._preliminary = value; this.recompute(); }
  @Input() set label(val: string | null | undefined) { this._aiLabel = val ?? null; this.recompute(); }
  @Input() set overallVerdict(val: OverallVerdict | null | undefined) { this._overallVerdict = val ?? null; this.recompute(); }
  @Input() set sourceStatus(val: SourceStatus | null | undefined) { this._sourceStatus = val ?? null; this.recompute(); }
  @Input() set headlineStatus(val: HeadlineAlterationStatus | null | undefined) { this._headlineStatus = val ?? null; this.recompute(); }
  @Input() set contentStatus(val: ContentStatus | null | undefined) { this._contentStatus = val ?? null; this.recompute(); }
  @Input() set dateStatus(val: DateStatus | null | undefined) { this._dateStatus = val ?? null; this.recompute(); }
  @Input() set hideDate(val: boolean) { this._hideDate = val; this.recompute(); }

  private _aiLabel: string | null = null;
  private _overallVerdict: OverallVerdict | null = null;
  private _sourceStatus: SourceStatus | null = null;
  private _headlineStatus: HeadlineAlterationStatus | null = null;
  private _contentStatus: ContentStatus | null = null;
  private _dateStatus: DateStatus | null = null;
  private _hideDate = false;

  badges: BadgeConfig[] = [];

  private recompute(): void {
    const badges: BadgeConfig[] = [];
    if (this._overallVerdict) {
      badges.push(this._preliminary
        ? { text: `AI: ${aiDecisionLabel(this._overallVerdict)}`, cls: 'badge-pending', icon: '' }
        : OVERALL_CONFIG[this._overallVerdict]);
    }
    if (this._sourceStatus === 'NOT_FOUND') {
      badges.push({ text: NOT_FOUND_IN_CLAIMED_SOURCE, cls: 'badge-not-found', icon: '' });
    } else if (this._sourceStatus === 'INCOMPLETE') {
      badges.push({ text: 'Source check incomplete', cls: 'badge-incomplete', icon: '?' });
    } else if (this._sourceStatus === 'CONFIRMED' || !this._sourceStatus) {
      if (this._headlineStatus) badges.push(HEADLINE_CONFIG[this._headlineStatus]);
      else if (this._contentStatus) badges.push(CONTENT_CONFIG[this._contentStatus]);
      if (this._dateStatus && !this._hideDate) badges.push(DATE_CONFIG[this._dateStatus]);
    }
    if (!badges.length && this._aiLabel) {
      badges.push({ text: `AI: ${aiDecisionLabel(this._aiLabel)}`, cls: 'badge-pending', icon: '' });
    }
    this.badges = badges.filter(Boolean);
  }
}
