import { readableExplanation } from '../../utils/presentation';
import { DatePipe, NgClass, NgTemplateOutlet } from '@angular/common';
import { Component, Input } from '@angular/core';
import {
  ClaimScope,
  ManipulationFlags,
  VerificationResponse,
  VerificationScores,
  AnalysisDetails,
} from '../../../models/verification.model';
import {
  STRENGTH_HELP,
  STRENGTH_LABEL,
  buildCheckRows,
  buildScoreRows,
  hasBody,
  strengthFor,
} from '../../utils/result-view';
import { VerdictBadgeComponent } from '../verdict-badge/verdict-badge.component';

/**
 * Alteration checks. Only a COMPLETED PASSING check renders as a green tick;
 * checks that could not run are neutral "not evaluated"; inapplicable checks
 * (e.g. any submitted-body check on a photo card) are omitted. Every failure
 * lists the claim/source text that disagrees.
 */
@Component({
  selector: 'app-result-checks',
  standalone: true,
  imports: [NgClass],
  styleUrls: ['./verification-report.component.scss'],
  template: `
    @if (rows.length) {
      <div class="checks-section">
        <h4>Recorded comparison checks</h4>
        <div class="checks-grid">
          @for (row of rows; track row.key) {
            <div class="check-card" [ngClass]="row.cls">
              <div class="check-icon-wrap" [attr.aria-label]="row.cls === 'passed' ? 'Matched' : row.cls === 'failed' ? 'Difference found' : 'Not evaluated'">{{ row.icon }}</div>
              <div class="check-body">
                <span class="check-title">{{ row.title }}</span>
                <span class="check-desc">{{ row.desc }}</span>
                @for (d of row.discrepancies; track $index) {
                  <div class="discrepancy">
                    <strong>{{ readableExplanation(d.detail) }}</strong>
                    <div class="disc-quote">Claim: “{{ d.claim_text }}”</div>
                    @if (d.evidence_text) {
                      <div class="disc-quote">Source: “{{ d.evidence_text }}”</div>
                    }
                  </div>
                }
              </div>
            </div>
          }
        </div>
      </div>
    }
  `,
})
export class ResultChecksComponent {
  readonly readableExplanation = readableExplanation;
  @Input() flags: ManipulationFlags | null | undefined;
  @Input() scope: ClaimScope | null | undefined;

  get rows() {
    return buildCheckRows(this.flags, this.scope);
  }
}

/**
 * Component scores for the claim vs the claimed source. A missing measurement
 * is shown as "Not applicable" / "Unavailable" with its reason - never as
 * 0% or 100%. Body metrics exist only for claims that carried a body.
 */
@Component({
  selector: 'app-result-scores',
  standalone: true,
  styleUrls: ['./verification-report.component.scss'],
  template: `
    @if (rows.length) {
      <div class="scores-grid">
        @for (row of rows; track row.key) {
          <div class="score-item" [class.score-missing]="row.value === null">
            <div class="score-info">
              <span class="score-label" [attr.title]="row.hint">{{ row.label }} ℹ</span>
              <span class="score-value" [class.muted]="row.value === null">{{ row.display }}</span>
            </div>
            @if (row.value !== null) {
              <div class="progress-bar-wrap">
                <div class="progress-bar" [style.width.%]="row.value * 100" [style.background]="row.color"></div>
              </div>
            } @else if (row.note) {
              <span class="score-note">{{ readableExplanation(row.note) }}</span>
            }
          </div>
        }
      </div>
    }
  `,
})
export class ResultScoresComponent {
  readonly readableExplanation = readableExplanation;
  @Input() scores: VerificationScores | null | undefined;
  @Input() analysis: AnalysisDetails | null | undefined;
  @Input() scope: ClaimScope | null | undefined;

  get rows() {
    return buildScoreRows(this.scores, this.analysis, this.scope);
  }
}

/**
 * The saved automated result for a SOURCE_BASED or PHOTO_CARD submission.
 * Before expert finalization it shows a "review pending" notice and NO overall
 * truth badge; afterwards the expert verdict and finalized dimensions, with
 * the automated result still inspectable.
 */
@Component({
  selector: 'app-verification-report',
  standalone: true,
  imports: [DatePipe, NgTemplateOutlet, VerdictBadgeComponent, ResultChecksComponent, ResultScoresComponent],
  styleUrls: ['./verification-report.component.scss'],
  templateUrl: './verification-report.component.html',
})
export class VerificationReportComponent {
  @Input({ required: true }) r!: VerificationResponse;
  @Input() reviewer = false;
  get hasCheckDetails(): boolean { return !!Object.keys(this.r.manipulation_flags.check_states || {}).length; }

  readonly strengthLabel = STRENGTH_LABEL;
  readonly strengthHelp = STRENGTH_HELP;

  get bodyApplicable(): boolean {
    return hasBody(this.r.claim_scope);
  }

  get scopeLabel(): string {
    return this.bodyApplicable ? 'Headline + submitted body' : 'Headline only';
  }

  get scopeHelp(): string {
    return this.bodyApplicable
      ? 'The submitted headline and body were both compared with the source report.'
      : 'Only the headline was compared with the source report; no body was submitted.';
  }

  get strength(): string {
    return strengthFor(this.r.confidence, this.r.source_status);
  }

  get dashOffset(): number {
    const c = this.r.source_status === 'INCOMPLETE' ? 0 : this.r.confidence || 0;
    return 283 - 283 * c;
  }

  get ringColor(): string {
    if (this.r.source_status === 'CONFIRMED' && this.r.content_status === 'MATCHED') return '#10b981';
    if (this.r.source_status === 'CONFIRMED' && this.r.content_status === 'ALTERED') return '#f59e0b';
    return '#6b7280';
  }

  host(url: string): string {
    try {
      return new URL(url).hostname.replace('www.', '');
    } catch {
      return '';
    }
  }
}
