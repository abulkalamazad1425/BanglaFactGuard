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
  NOT_FOUND_IN_VERIFIED_SOURCES,
  SOURCE_EXPLANATIONS,
  SOURCE_LABELS,
  SOURCE_QUESTION,
  SOURCE_RESOLUTION_NOTES,
  VERIFIED_SOURCE_EXPLANATIONS,
  VERIFIED_SOURCES_QUESTION,
} from '../../utils/status-labels';

export const MAX_EVIDENCE_ARTICLES = 3;
import { VerdictBadgeComponent } from '../verdict-badge/verdict-badge.component';
import { VotingDetailsComponent } from '../voting-details/voting-details.component';

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
  @Input({ required: true }) r!: VerificationResponse;
  @Input() reviewer = false;
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

  get articleFound(): boolean {
    return this.r.source_status === 'CONFIRMED';
  }

  get sourceLabel(): string {
    return SOURCE_LABELS[this.r.source_status];
  }

  get verifiedMode(): boolean {
    return this.r.verification_mode === 'VERIFIED_SOURCES';
  }

  get sourceQuestion(): string {
    return this.verifiedMode ? VERIFIED_SOURCES_QUESTION : SOURCE_QUESTION;
  }

  get notFoundText(): string {
    return this.verifiedMode ? NOT_FOUND_IN_VERIFIED_SOURCES : NOT_FOUND_IN_CLAIMED_SOURCE;
  }

  get sourceExplanation(): string {
    return this.verifiedMode
      ? VERIFIED_SOURCE_EXPLANATIONS[this.r.source_status]
      : SOURCE_EXPLANATIONS[this.r.source_status];
  }

  get resolutionNote(): string | null {
    if (!this.verifiedMode) return null;
    const reason = this.r.source_resolution_reason ?? '';
    return (
      SOURCE_RESOLUTION_NOTES[reason] ??
      'No usable claimed outlet was available, so the active verified news sources were searched.'
    );
  }

  get incompleteReason(): string | null {
    return this.r.source_status === 'INCOMPLETE'
      ? (this.r.analysis?.source_scope?.incomplete_reason ?? null)
      : null;
  }

  get evidence() {
    const seen = new Set<string>();
    const out = [];
    const sorted = [...this.r.matched_articles].sort(
      (a, b) => Number(!!b.is_primary) - Number(!!a.is_primary),
    );
    for (const art of sorted) {
      const key = art.url.replace(/\/+$/, '').toLowerCase();
      if (seen.has(key)) continue;
      seen.add(key);
      out.push(art);
      if (out.length >= MAX_EVIDENCE_ARTICLES) break;
    }
    return out;
  }

  get evidenceHeading(): string {
    if (!this.articleFound) return 'What the source search returned';
    return this.verifiedMode
      ? 'Relevant articles from verified sources'
      : 'Relevant article from claimed source';
  }

  get claimedPublishedDate(): string | null {
    return (
      this.r.claimed_published_date ??
      this.claimedDate ??
      this.r.analysis?.date?.claimed_date ??
      null
    );
  }

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
