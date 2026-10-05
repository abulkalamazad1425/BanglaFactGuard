import { DatePipe, NgClass, NgTemplateOutlet } from '@angular/common';
import { Component, Input } from '@angular/core';
import { RouterLink } from '@angular/router';
import { VerificationResponse } from '../../../models/verification.model';
import { readableExplanation } from '../../utils/presentation';
import {
  bodySectionMessage,
  buildBodyMetricRows,
  buildCorrespondenceRows,
  differenceLabel,
  formatPercent,
  hasBody,
  headlineView,
} from '../../utils/result-view';
import { VerdictBadgeComponent } from '../verdict-badge/verdict-badge.component';

/**
 * The saved automated result for a SOURCE_BASED or PHOTO_CARD submission.
 * Findings are shown separately: Source, Headline Alteration (claim headline
 * vs source title only), Date, and — for claims with a body — the four body
 * similarity scores, which are measurements and never a verdict. Before
 * expert finalization there is a "review pending" notice and no overall
 * truth badge.
 */
@Component({
  selector: 'app-verification-report',
  standalone: true,
  imports: [DatePipe, NgClass, NgTemplateOutlet, RouterLink, VerdictBadgeComponent],
  styleUrls: ['./verification-report.component.scss'],
  templateUrl: './verification-report.component.html',
})
export class VerificationReportComponent {
  readonly readableExplanation = readableExplanation;
  readonly differenceLabel = differenceLabel;
  readonly formatPercent = formatPercent;
  @Input({ required: true }) r!: VerificationResponse;
  @Input() reviewer = false;

  get headline() {
    return headlineView(this.r);
  }

  get headlineDetail() {
    return this.r.legacy_result ? null : (this.r.analysis?.headline_alteration ?? null);
  }

  get bodyApplicable(): boolean {
    return hasBody(this.r.claim_scope);
  }

  get bodyRows() {
    return buildBodyMetricRows(this.r.analysis?.body_similarity);
  }

  get bodyMessage(): string | null {
    return bodySectionMessage(this.r.analysis?.body_similarity, this.r.claim_scope);
  }

  get correspondenceRows() {
    return buildCorrespondenceRows(this.r.analysis);
  }

  get scopeLabel(): string {
    return this.bodyApplicable ? 'Headline + submitted body' : 'Headline only';
  }

  get scopeHelp(): string {
    return this.bodyApplicable
      ? 'The headline is compared with the source title; the submitted body is measured separately for similarity.'
      : 'Only the headline was compared with the source title; no body was submitted.';
  }

  get sourceTitle(): string {
    return this.r.source_status === 'CONFIRMED'
      ? 'Source confirmed'
      : this.r.source_status === 'NOT_FOUND'
        ? 'Source not found'
        : 'Source check incomplete';
  }

  host(url: string): string {
    try {
      return new URL(url).hostname.replace('www.', '');
    } catch {
      return '';
    }
  }
}
