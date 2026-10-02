import { Component, Input } from '@angular/core';
import { NgClass } from '@angular/common';
import {
  ContentStatus,
  DateStatus,
  OverallVerdict,
  SourceStatus,
} from '../../../models/verification.model';

// Legacy single-category labels — kept only for any lingering display of the
// old flat TRUE/FALSE/PARTIALLY_TRUE/NOT_FOUND_IN_CLAIMED_SOURCE enum.
// Expert review now votes on the same (source/content/date) structure as the
// AI verdict model below, via [sourceStatus]/[contentStatus]/[dateStatus].
const LABEL_CONFIG: Record<string, { text: string; cls: string; icon: string }> = {
  'TRUE': { text: 'True', cls: 'badge-true', icon: '✓' },
  'FALSE': { text: 'False', cls: 'badge-false', icon: '✗' },
  'PARTIALLY_TRUE': { text: 'Partially True', cls: 'badge-partial', icon: '◑' },
  'NOT_FOUND_IN_CLAIMED_SOURCE': { text: 'Not Found', cls: 'badge-not-found', icon: '?' },
};

const SOURCE_CONFIG: Record<SourceStatus, { text: string; cls: string; icon: string }> = {
  CONFIRMED: { text: 'Source Confirmed', cls: 'badge-true', icon: '✓' },
  NOT_FOUND: { text: 'Source Not Found', cls: 'badge-not-found', icon: '?' },
  INCOMPLETE: { text: 'Source Check Incomplete', cls: 'badge-incomplete', icon: '⚠' },
};

const CONTENT_CONFIG: Record<ContentStatus, { text: string; cls: string; icon: string }> = {
  MATCHED: { text: 'Content Matched', cls: 'badge-true', icon: '✓' },
  ALTERED: { text: 'Content Altered', cls: 'badge-partial', icon: '◑' },
  INCOMPLETE: { text: 'Content Check Incomplete', cls: 'badge-incomplete', icon: '⚠' },
};

const DATE_CONFIG: Record<DateStatus, { text: string; cls: string; icon: string }> = {
  MATCHED: { text: 'Date Matched', cls: 'badge-true', icon: '✓' },
  MISMATCHED: { text: 'Date Mismatch', cls: 'badge-partial', icon: '📅' },
  INCOMPLETE: { text: 'Date Check Incomplete', cls: 'badge-incomplete', icon: '⚠' },
};

const OVERALL_CONFIG: Record<OverallVerdict, { text: string; cls: string; icon: string }> = {
  REAL: { text: 'Real', cls: 'badge-true', icon: '✓' },
  FAKE: { text: 'Fake', cls: 'badge-false', icon: '✗' },
  MISLEADING: { text: 'Misleading', cls: 'badge-partial', icon: '◑' },
  ALTERED: { text: 'Altered', cls: 'badge-partial', icon: '✎' },
};

type BadgeConfig = { text: string; cls: string; icon: string };

/**
 * Renders one or more verdict chips:
 * - `[overallVerdict]` — the Fake/Real/Misleading/Altered headline verdict,
 *   voted on for every submission type.
 * - `[sourceStatus]` / `[contentStatus]` / `[dateStatus]` — the additional
 *   structured verdict that exists for SOURCE_BASED/PHOTO_CARD claims only;
 *   renders alongside overallVerdict when both are passed.
 * - `[label]` — a single legacy badge, used only as a fallback when neither
 *   of the above is set.
 */
@Component({
  selector: 'app-verdict-badge',
  standalone: true,
  imports: [NgClass],
  template: `
    @for (badge of badges; track badge.text) {
      <span class="badge" [ngClass]="badge.cls">
        <span class="badge-icon">{{ badge.icon }}</span>
        {{ badge.text }}
      </span>
    }
  `,
  host: { '[class.inline]': 'true' },
  styles: [`
    :host { display: inline-flex; gap: 6px; flex-wrap: wrap; }
    .badge-icon { font-weight: 700; }
  `],
})
export class VerdictBadgeComponent {
  @Input() set label(val: string | null | undefined) {
    this._legacyLabel = val ?? null;
    this.recompute();
  }

  @Input() set overallVerdict(val: OverallVerdict | null | undefined) {
    this._overallVerdict = val ?? null;
    this.recompute();
  }

  @Input() set sourceStatus(val: SourceStatus | null | undefined) {
    this._sourceStatus = val ?? null;
    this.recompute();
  }

  @Input() set contentStatus(val: ContentStatus | null | undefined) {
    this._contentStatus = val ?? null;
    this.recompute();
  }

  @Input() set dateStatus(val: DateStatus | null | undefined) {
    this._dateStatus = val ?? null;
    this.recompute();
  }

  private _legacyLabel: string | null = null;
  private _overallVerdict: OverallVerdict | null = null;
  private _sourceStatus: SourceStatus | null = null;
  private _contentStatus: ContentStatus | null = null;
  private _dateStatus: DateStatus | null = null;

  badges: BadgeConfig[] = [];

  private recompute(): void {
    // overallVerdict and sourceStatus/contentStatus/dateStatus can be shown
    // together (SOURCE_BASED/PHOTO_CARD carry both); legacy [label] is a
    // fallback only used when neither of the above is set.
    if (this._overallVerdict || this._sourceStatus) {
      const badges: BadgeConfig[] = [];
      if (this._overallVerdict) badges.push(OVERALL_CONFIG[this._overallVerdict]);
      if (this._sourceStatus) badges.push(SOURCE_CONFIG[this._sourceStatus]);
      if (this._contentStatus) badges.push(CONTENT_CONFIG[this._contentStatus]);
      if (this._dateStatus) badges.push(DATE_CONFIG[this._dateStatus]);
      this.badges = badges.filter(Boolean);
      return;
    }

    if (this._legacyLabel) {
      const config = LABEL_CONFIG[this._legacyLabel];
      this.badges = config ? [config] : [];
      return;
    }

    this.badges = [];
  }
}
