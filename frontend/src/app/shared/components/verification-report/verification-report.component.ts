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
  headlineStatusOf,
  headlineView,
} from '../../utils/result-view';
import {
  DATE_EXPLANATIONS,
  DATE_LABELS,
  NOT_FOUND_IN_CLAIMED_SOURCE,
  SOURCE_EXPLANATIONS,
  SOURCE_LABELS,
  SOURCE_QUESTION,
} from '../../utils/status-labels';
import { VerdictBadgeComponent } from '../verdict-badge/verdict-badge.component';
import { VotingDetailsComponent } from '../voting-details/voting-details.component';

/**
 * The saved result for a SOURCE_BASED or PHOTO_CARD submission, in two
 * clearly separated parts:
 *  1. Final decision — the reviewers' overall verdict (or an admin's, for an
 *     escalated claim) with public Voting Details; "under review" until then.
 *  2. Preliminary AI verification — "Relevant article from claimed source"
 *     (Found / Not Found), then, only when found, the headline status (Exact
 *     Matched / Meaning Preserved / Altered), the date comparison (only when
 *     a date was claimed) and the body similarity measurements.
 */
@Component({
  selector: 'app-verification-report',
  standalone: true,
  imports: [
    DatePipe,
    NgClass,
    NgTemplateOutlet,
    RouterLink,
    VerdictBadgeComponent,
    VotingDetailsComponent,
  ],
  styleUrls: ['./verification-report.component.scss'],
  templateUrl: './verification-report.component.html',
})
export class VerificationReportComponent {
  readonly readableExplanation = readableExplanation;
  readonly differenceLabel = differenceLabel;
  readonly formatPercent = formatPercent;
  readonly SOURCE_QUESTION = SOURCE_QUESTION;
  readonly NOT_FOUND_IN_CLAIMED_SOURCE = NOT_FOUND_IN_CLAIMED_SOURCE;
  @Input({ required: true }) r!: VerificationResponse;
  @Input() reviewer = false;
  /** Fallback when an older response lacks claimed_published_date. */
  @Input() claimedDate: string | null | undefined = undefined;

  get headline() {
    return headlineView(this.r);
  }

  get headlineStatus() {
    return headlineStatusOf(this.r);
  }

  get headlineDetail() {
    return this.r.legacy_result ? null : (this.r.analysis?.headline_alteration ?? null);
  }

  /** Headline, date and body findings only exist once a relevant article was found. */
  get articleFound(): boolean {
    return this.r.source_status === 'CONFIRMED';
  }

  get sourceLabel(): string {
    return SOURCE_LABELS[this.r.source_status];
  }

  get sourceExplanation(): string {
    return SOURCE_EXPLANATIONS[this.r.source_status];
  }

  get claimedPublishedDate(): string | null {
    return (
      this.r.claimed_published_date ??
      this.claimedDate ??
      this.r.analysis?.date?.claimed_date ??
      null
    );
  }

  /** Date comparison is part of the result only when the submitter claimed a date. */
  get showDate(): boolean {
    return this.articleFound && !!this.claimedPublishedDate;
  }

  get dateLabel(): string {
    return this.r.date_status ? DATE_LABELS[this.r.date_status] : 'Not compared';
  }

  get dateExplanation(): string {
    return this.r.date_status
      ? DATE_EXPLANATIONS[this.r.date_status]
      : 'No source publication date was available to compare with.';
  }

  get bodyApplicable(): boolean {
    return this.articleFound && hasBody(this.r.claim_scope);
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
    return hasBody(this.r.claim_scope) ? 'Headline + submitted body' : 'Headline only';
  }

  get scopeHelp(): string {
    return hasBody(this.r.claim_scope)
      ? 'The headline is compared with the source title; the submitted body is measured separately for similarity.'
      : 'Only the headline was compared with the source title; no body was submitted.';
  }

  host(url: string): string {
    try {
      return new URL(url).hostname.replace('www.', '');
    } catch {
      return '';
    }
  }
}
