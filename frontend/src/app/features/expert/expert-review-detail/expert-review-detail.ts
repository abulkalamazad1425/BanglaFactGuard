import { Component, OnInit, inject, signal, computed } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { CommonModule } from '@angular/common';
import { ExpertService } from '../../../services/expert.service';
import { ToastService } from '../../../shared/services/toast.service';
import { ExpertQueueItem } from '../../../models/expert.model';
import { VerificationResponse, MatchedArticle } from '../../../models/verification.model';
import { VerdictBadgeComponent } from '../../../shared/components/verdict-badge/verdict-badge.component';
import { ScoreBarComponent } from '../../../shared/components/score-bar/score-bar.component';
import {
  ResultChecksComponent,
  ResultScoresComponent,
} from '../../../shared/components/verification-report/verification-report.component';
import { VerificationService } from '../../../services/verification.service';
import { AuthService } from '../../../services/auth.service';
import { SourceStatus, ContentStatus, DateStatus, OverallVerdict } from '../../../models/verification.model';

const OVERALL_VERDICTS: { value: OverallVerdict; label: string; icon: string; cls: string }[] = [
  { value: 'REAL', label: 'Real', icon: '✓', cls: 'option-true' },
  { value: 'FAKE', label: 'Fake', icon: '✗', cls: 'option-false' },
  { value: 'MISLEADING', label: 'Misleading', icon: '◑', cls: 'option-partial' },
  { value: 'ALTERED', label: 'Altered', icon: '✎', cls: 'option-partial' },
];

@Component({
  selector: 'app-expert-review-detail',
  standalone: true,
  imports: [
    CommonModule,
    ReactiveFormsModule,
    RouterLink,
    VerdictBadgeComponent,
    ScoreBarComponent,
    ResultChecksComponent,
    ResultScoresComponent,
  ],
  templateUrl: './expert-review-detail.html',
  styleUrls: ['./expert-review-detail.scss']
})
export class ExpertReviewDetailComponent implements OnInit {
  private readonly expertSvc = inject(ExpertService);
  private readonly verificationSvc = inject(VerificationService);
  private readonly route = inject(ActivatedRoute);
  private readonly toast = inject(ToastService);
  private readonly fb = inject(FormBuilder);
  private readonly auth = inject(AuthService);

  readonly isAdmin = this.auth.isAdmin;
  readonly overallOptions = OVERALL_VERDICTS;

  readonly loading = signal(true);
  readonly voting = signal(false);
  readonly submitted = signal(false);
  readonly claim = signal<ExpertQueueItem | null>(null);
  readonly aiResult = signal<VerificationResponse | null>(null);

  readonly selectedOverall = signal<OverallVerdict | null>(null);
  readonly selectedSource = signal<SourceStatus | null>(null);
  readonly selectedContent = signal<ContentStatus | null>(null);
  readonly selectedDate = signal<DateStatus | null>(null);
  formSubmitted = false;

  /** Source/Content/Date only apply to SOURCE_BASED/PHOTO_CARD claims — every
   *  type votes on Overall, but multimodal has no structured sub-dimensions. */
  readonly isStructuredType = computed(() => this.claim()?.submission_type !== 'MULTIMODAL');
  readonly needsContentAndDate = computed(() => this.selectedSource() === 'CONFIRMED');

  // Requirement: at most one top article is ever surfaced on this page, with its full body.
  readonly topArticle = computed<MatchedArticle | null>(() => {
    const articles = this.aiResult()?.matched_articles;
    return articles && articles.length > 0 ? articles[0] : null;
  });

  form = this.fb.group({
    justification: ['', [Validators.required, Validators.minLength(50)]],
  });

  get justInvalid() { return this.form.get('justification')?.invalid && this.form.get('justification')?.touched; }
  get charCount() { return (this.form.value.justification || '').length; }

  selectOverall(val: OverallVerdict): void { this.selectedOverall.set(val); }

  selectSource(val: SourceStatus): void {
    this.selectedSource.set(val);
    if (val === 'NOT_FOUND') {
      // Content/Date are moot once the source itself isn't confirmed.
      this.selectedContent.set(null);
      this.selectedDate.set(null);
    }
  }

  selectContent(val: ContentStatus): void { this.selectedContent.set(val); }
  selectDate(val: DateStatus): void { this.selectedDate.set(val); }

  /** True once the vote is complete enough to submit. Overall is always
   *  required; Source (and, if Confirmed, Content/Date) are only required
   *  for SOURCE_BASED/PHOTO_CARD claims. */
  readonly voteComplete = computed(() => {
    if (!this.selectedOverall()) return false;
    if (!this.isStructuredType()) return true;

    const source = this.selectedSource();
    if (!source) return false;
    if (source === 'NOT_FOUND') return true;
    return !!this.selectedContent() && !!this.selectedDate();
  });

  /** A non-blocking heads-up when Overall and the structured sub-verdicts
   *  seem to pull in different directions — the expert's own editorial call
   *  on Overall always wins, this is just a sanity nudge. */
  readonly inconsistencyWarning = computed<string | null>(() => {
    const overall = this.selectedOverall();
    if (!overall || !this.isStructuredType()) return null;
    const source = this.selectedSource();
    const content = this.selectedContent();

    if (overall === 'REAL' && source === 'NOT_FOUND') {
      return 'Overall is "Real" but Source is "Not Found" — usually a claimed source that never ran the story points toward Fake.';
    }
    if (overall === 'REAL' && content === 'ALTERED') {
      return 'Overall is "Real" but Content is "Altered" — consider whether Misleading or Altered fits the Overall verdict better.';
    }
    if (overall === 'FAKE' && source === 'CONFIRMED' && content === 'MATCHED') {
      return 'Overall is "Fake" even though Source is confirmed and Content matches — double-check this is intended.';
    }
    if (overall === 'ALTERED' && content === 'MATCHED') {
      return 'Overall is "Altered" but Content is "Matched" — consider whether Real fits better if nothing was actually changed.';
    }
    return null;
  });

  ngOnInit(): void {
    const claimId = this.route.snapshot.paramMap.get('id');
    if (!claimId) { this.loading.set(false); return; }

    this.expertSvc.getQueueItem(claimId).subscribe({
      next: c => {
        this.claim.set(c);

        if (c.submission_type === 'MULTIMODAL') {
          // No separate "detailed AI result" endpoint for multimodal — the
          // queue item already carries everything (image, AI label, confidence).
          this.loading.set(false);
          return;
        }

        // Also fetch the full AI prediction details (includes full article bodies)
        this.verificationSvc.getResult(claimId).subscribe({
          next: res => { this.aiResult.set(res); this.loading.set(false); },
          error: () => { this.loading.set(false); }
        });
      },
      error: () => this.loading.set(false),
    });
  }

  onSubmit(): void {
    if (this.isAdmin()) { return; } // administrators may view but never vote
    this.formSubmitted = true;
    if (this.form.invalid || !this.voteComplete()) {
      this.form.markAllAsTouched();
      return;
    }
    const claimId = this.route.snapshot.paramMap.get('id');
    if (!claimId) return;
    this.voting.set(true);

    this.expertSvc.submitVote(claimId, {
      overall_verdict: this.selectedOverall()!,
      source_status: this.isStructuredType() ? this.selectedSource() : null,
      content_status: this.isStructuredType() ? this.selectedContent() : null,
      date_status: this.isStructuredType() ? this.selectedDate() : null,
      justification: this.form.value.justification as string,
    }).subscribe({
      next: () => { this.submitted.set(true); this.voting.set(false); this.toast.success('Vote submitted successfully!'); },
      error: err => { this.voting.set(false); this.toast.error(err.error?.message || 'Failed to submit vote.'); },
    });
  }

  getHost(url: string): string {
    try {
      return new URL(url).hostname.replace('www.', '');
    } catch {
      return '';
    }
  }
}
