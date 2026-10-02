import { DatePipe, NgClass } from '@angular/common';
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
        <h4>🔍 Alteration checks</h4>
        <div class="checks-grid">
          @for (row of rows; track row.key) {
            <div class="check-card" [ngClass]="row.cls">
              <div class="check-icon-wrap" [attr.aria-label]="row.state">{{ row.icon }}</div>
              <div class="check-body">
                <span class="check-title">{{ row.title }}</span>
                <span class="check-desc">{{ row.desc }}</span>
                @for (d of row.discrepancies; track $index) {
                  <div class="discrepancy">
                    <strong>{{ d.detail }}</strong>
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
              <span class="score-note">{{ row.note }}</span>
            }
          </div>
        }
      </div>
    }
  `,
})
export class ResultScoresComponent {
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
  imports: [DatePipe, NgClass, VerdictBadgeComponent, ResultChecksComponent, ResultScoresComponent],
  styleUrls: ['./verification-report.component.scss'],
  template: `
    <div class="verdict-header">
      <div class="verdict-left">
        @if (r.is_finalized && r.overall_verdict) {
          <div class="overall-verdict-row">
            <span class="badge badge-true">⚖️ Expert verified</span>
            <app-verdict-badge [overallVerdict]="r.overall_verdict" />
          </div>
        } @else {
          <div class="review-pending">
            <span class="badge badge-pending">⏳ Awaiting expert review</span>
            <span class="review-pending-note">
              Preliminary automated result — Source, Content and Date only. Fake / Real /
              Misleading / Altered is decided by experts and is not shown yet.
            </span>
          </div>
        }
        <app-verdict-badge
          [sourceStatus]="r.source_status"
          [contentStatus]="r.content_status"
          [dateStatus]="r.date_status" />
        <div class="source-info">
          Claimed source: <strong>{{ r.normalized_source || '' }}</strong>
          <span class="scope-tag" [title]="scopeHelp">{{ scopeLabel }}</span>
          @if (r.cached) { <span class="cache-tag">⚡ Previous result reused</span> }
        </div>
      </div>

      <div class="confidence-meter" [title]="strengthHelp">
        <svg class="confidence-svg" viewBox="0 0 100 100" aria-hidden="true">
          <circle class="bg-ring" cx="50" cy="50" r="45"></circle>
          <circle class="progress-ring" cx="50" cy="50" r="45"
                  [style.stroke-dashoffset]="dashOffset"
                  [style.stroke]="ringColor"></circle>
        </svg>
        <div class="confidence-text">
          <span class="confidence-val">{{ strength }}</span>
          <span class="confidence-lbl">{{ strengthLabel }}</span>
        </div>
      </div>
    </div>

    @if (r.was_overridden) {
      <div class="override-banner">
        ⚖️ Experts changed the automated finding after review. The automated call was
        <app-verdict-badge
          [sourceStatus]="r.ai_source_status"
          [contentStatus]="r.ai_content_status"
          [dateStatus]="r.ai_date_status" />
        — the structured result above is the expert-reviewed status.
      </div>
    }

    @if (r.reasoning) {
      <div class="reasoning-box">
        <h4>💬 Why this result</h4>
        <p>{{ r.reasoning }}</p>
        @if (r.analysis?.source_basis?.length && r.source_status !== 'CONFIRMED') {
          <ul class="basis-list">
            @for (b of r.analysis!.source_basis; track $index) { <li>{{ b }}</li> }
          </ul>
        }
      </div>
    }

    <!-- Search coverage matters most when nothing was confirmed -->
    @if (r.source_status !== 'CONFIRMED' && r.analysis?.search; as s) {
      <div class="search-summary">
        🔎 Search coverage: {{ s.success + s.cached }} call(s) returned results,
        {{ s.success_empty }} completed with none, {{ s.failed }} failed
        @if (s.skipped) { , {{ s.skipped }} skipped (not configured) }.
      </div>
    }

    @if (r.source_status === 'CONFIRMED') {
      <h4 class="section-title">Content match against the claimed source</h4>
      <p class="section-sub">
        Measurements of how the submitted
        {{ bodyApplicable ? 'headline and body compare' : 'headline compares' }} with the report found on
        {{ r.normalized_source || 'the source' }}. They describe agreement with that report, not whether
        the claim is true elsewhere.
      </p>
      <app-result-scores [scores]="r.scores" [analysis]="r.analysis" [scope]="r.claim_scope" />

      <!-- Content Altered must show what was altered -->
      @if (r.ai_content_status === 'ALTERED' && (r.manipulation_flags.discrepancies?.length ?? 0) === 0) {
        <div class="alert-note">
          This older result is marked Altered but no itemised discrepancy was recorded for it.
        </div>
      }
      <app-result-checks [flags]="r.manipulation_flags" [scope]="r.claim_scope" />

      @if (r.analysis?.date; as d) {
        <div class="date-compare" [ngClass]="r.ai_date_status ? 'date-' + r.ai_date_status.toLowerCase() : ''">
          <h4>📅 Publication date</h4>
          @if (!d.claimed_date) {
            <p>No publication date was claimed, so the date check does not apply.</p>
          } @else {
            <p>
              Claimed <strong>{{ d.claimed_date | date: 'MMM d, y' }}</strong> ·
              Report published
              <strong>{{ d.article_date ? (d.article_date | date: 'MMM d, y') : 'unknown' }}</strong>
              (Asia/Dhaka)
              @if (d.provenance) { <span class="prov">via {{ d.provenance }}</span> }
              @if (d.tz_assumed) { <span class="prov">· timezone assumed</span> }
            </p>
          }
        </div>
      }
    }

    @if (r.matched_articles && r.matched_articles.length) {
      <div class="articles-section">
        <h4 class="section-title">
          📰 {{ r.source_status === 'CONFIRMED' ? 'Corresponding report on the claimed source' : 'Closest article retrieved (not a match)' }}
        </h4>
        @for (art of r.matched_articles.slice(0, 1); track art.url) {
          <div class="article-card">
            <div class="article-header">
              <a [href]="art.url" target="_blank" rel="noopener" class="article-title">
                {{ art.title || 'View source article' }}
              </a>
              @if (art.rank_score != null) {
                <div class="article-match" title="How likely this is the report the claim is about — retrieval relevance, not a content-match score.">
                  Retrieval relevance: {{ (art.rank_score * 100).toFixed(0) }}%
                </div>
              }
            </div>
            <div class="article-meta">
              @if (art.author) { <span>👤 {{ art.author }}</span> }
              @if (art.published_date) { <span>📅 {{ art.published_date }}</span> }
              <span>🌐 {{ host(art.url) }}</span>
            </div>
            @if (art.body) {
              <a [href]="art.url" target="_blank" rel="noopener" class="article-snippet-link">
                <p class="article-snippet">{{ art.body }}</p>
              </a>
            }
          </div>
        }
      </div>
    }

    @if (r.processing_time_ms != null) {
      <div class="result-footer">
        Processed in {{ (r.processing_time_ms / 1000).toFixed(1) }}s on {{ r.created_at | date: 'medium' }}
      </div>
    }
  `,
})
export class VerificationReportComponent {
  @Input({ required: true }) r!: VerificationResponse;

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
