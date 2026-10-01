import { Component, Input } from '@angular/core';
import { NgClass } from '@angular/common';
import {
  ContentStatus,
  DateStatus,
  SourceStatus,
} from '../../../models/verification.model';

// Legacy single-category labels — still used by the independent expert-review
// voting system (ExpertLabel), which predates and is unrelated to the 3-status
// AI verdict model below.
const LABEL_CONFIG: Record<string, { text: string; cls: string; icon: string }> = {
  'TRUE': { text: 'True', cls: 'badge-true', icon: '✓' },
  'FALSE': { text: 'False', cls: 'badge-false', icon: '✗' },
  'PARTIALLY_TRUE': { text: 'Partially True', cls: 'badge-partial', icon: '◑' },
  'NOT_FOUND_IN_CLAIMED_SOURCE': { text: 'Not Found', cls: 'badge-not-found', icon: '?' },
};

const SOURCE_CONFIG: Record<SourceStatus, { text: string; cls: string; icon: string }> = {
  CONFIRMED: { text: 'Source Confirmed', cls: 'badge-true', icon: '✓' },
  NOT_FOUND: { text: 'Source Not Found', cls: 'badge-not-found', icon: '?' },
};

const CONTENT_CONFIG: Record<ContentStatus, { text: string; cls: string; icon: string }> = {
  MATCHED: { text: 'Content Matched', cls: 'badge-true', icon: '✓' },
  ALTERED: { text: 'Content Altered', cls: 'badge-partial', icon: '◑' },
};

const DATE_CONFIG: Record<DateStatus, { text: string; cls: string; icon: string }> = {
  MATCHED: { text: 'Date Matched', cls: 'badge-true', icon: '✓' },
  MISMATCHED: { text: 'Date Mismatch', cls: 'badge-partial', icon: '📅' },
};

type BadgeConfig = { text: string; cls: string; icon: string };

/**
 * Renders either:
 * - a single legacy badge, via `[label]` — used by expert review's own
 *   TRUE/FALSE/PARTIALLY_TRUE/NOT_FOUND_IN_CLAIMED_SOURCE vote category, or
 * - up to three badges for the AI pipeline's real verdict, via
 *   `[sourceStatus]` / `[contentStatus]` / `[dateStatus]` — these are
 *   independent dimensions, so each renders its own chip rather than being
 *   collapsed into one label.
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
  private _sourceStatus: SourceStatus | null = null;
  private _contentStatus: ContentStatus | null = null;
  private _dateStatus: DateStatus | null = null;

  badges: BadgeConfig[] = [];

  private recompute(): void {
    if (this._sourceStatus) {
      const badges: BadgeConfig[] = [SOURCE_CONFIG[this._sourceStatus]];
      if (this._contentStatus) badges.push(CONTENT_CONFIG[this._contentStatus]);
      if (this._dateStatus) badges.push(DATE_CONFIG[this._dateStatus]);
      this.badges = badges;
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
