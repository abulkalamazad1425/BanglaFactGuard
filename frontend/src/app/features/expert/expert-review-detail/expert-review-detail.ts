import { requestError, predictionLabel } from '../../../shared/utils/presentation';
import { PhotoCardService } from '../../../services/photocard.service';
import { PhotoCardResultResponse } from '../../../models/photocard.model';
import { Component, OnInit, inject, signal, computed } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { CommonModule } from '@angular/common';
import { ExpertService } from '../../../services/expert.service';
import { ToastService } from '../../../shared/services/toast.service';
import { ExpertQueueItem } from '../../../models/expert.model';
import { VerificationResponse } from '../../../models/verification.model';
import { VerificationReportComponent } from '../../../shared/components/verification-report/verification-report.component';
import { VerificationService } from '../../../services/verification.service';
import { AuthService } from '../../../services/auth.service';
import { SourceStatus, ContentStatus, DateStatus, OverallVerdict } from '../../../models/verification.model';

const OVERALL_VERDICTS: { value: OverallVerdict; label: string; icon: string }[] = [
  { value: 'REAL', label: 'Real', icon: '✓' },
  { value: 'FAKE', label: 'Fake', icon: '✗' },
  { value: 'MISLEADING', label: 'Misleading', icon: '◑' },
  { value: 'ALTERED', label: 'Altered', icon: '✎' },
];

/**
 * One claim's review workspace. Experts vote on open claims. An admin opens
 * the same page from the admin review queue: on an ESCALATED claim the
 * admin's overall vote is the final decision; every other claim is view-only.
 * Only the overall vote ("Cast your vote based on your findings") decides a
 * claim — the supplementary findings are optional and recorded for reference.
 */
@Component({
  selector: 'app-expert-review-detail',
  standalone: true,
  imports: [
    CommonModule,
    ReactiveFormsModule,
    RouterLink,
    VerificationReportComponent,
  ],
  templateUrl: './expert-review-detail.html',
  styleUrls: ['./expert-review-detail.scss']
})
export class ExpertReviewDetailComponent implements OnInit {
  readonly predictionLabel = predictionLabel;
  readonly loadError = signal(false);
  readonly forbidden = signal(false);
  readonly evidenceError = signal(false);
  readonly voteError = signal('');
  readonly photocardDetails = signal<PhotoCardResultResponse | null>(null);
  private readonly photocardSvc = inject(PhotoCardService);
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

  readonly queueLink = computed(() => this.isAdmin() ? '/admin/review-queue' : '/expert/queue');
  /** Source/headline/date findings only apply to SOURCE_BASED/PHOTO_CARD claims. */
  readonly isStructuredType = computed(() => this.claim()?.submission_type !== 'MULTIMODAL');
  readonly needsContentAndDate = computed(() => this.selectedSource() === 'CONFIRMED');
  readonly isAdminDecision = computed(() => this.isAdmin() && this.claim()?.decision_mode === 'ADMIN_FINAL');
  readonly canVote = computed(() => !!this.claim()?.can_vote);

  form = this.fb.group({
    justification: ['', [Validators.required, Validators.minLength(50)]],
  });

  get justInvalid() { return !!(this.form.get('justification')?.invalid && (this.form.get('justification')?.touched || this.formSubmitted)); }
  get charCount() { return (this.form.value.justification || '').length; }

  selectOverall(val: OverallVerdict): void { this.selectedOverall.set(val); }

  selectSource(val: SourceStatus | null): void {
    this.selectedSource.set(val);
    if (val !== 'CONFIRMED') {
      this.selectedContent.set(null);
      this.selectedDate.set(null);
    }
  }

  selectContent(val: ContentStatus | null): void { this.selectedContent.set(val); }
  selectDate(val: DateStatus | null): void { this.selectedDate.set(val); }

  /** Only the overall vote (plus the justification) is required. */
  readonly voteComplete = computed(() => !!this.selectedOverall());

  ngOnInit(): void {
    this.loadReview();
  }

  loadReview(): void {
    this.loading.set(true);
    this.loadError.set(false);
    this.forbidden.set(false);
    this.evidenceError.set(false);
    const claimId = this.route.snapshot.paramMap.get('id');
    if (!claimId) { this.loading.set(false); this.loadError.set(true); return; }

    this.expertSvc.getQueueItem(claimId).subscribe({
      next: c => {
        this.claim.set(c);
        if (c.submission_type === 'PHOTO_CARD') {
          this.photocardSvc.getResult(claimId).subscribe({ next: p => this.photocardDetails.set(p), error: () => this.evidenceError.set(true) });
        }

        if (c.submission_type === 'MULTIMODAL') {
          // No separate "detailed AI result" endpoint for multimodal — the
          // queue item already carries everything (image, AI label, confidence).
          this.loading.set(false);
          return;
        }

        this.verificationSvc.getResult(claimId).subscribe({
          next: res => { this.aiResult.set(res); this.loading.set(false); },
          error: () => { this.loading.set(false); this.evidenceError.set(true); }
        });
      },
      error: err => {
        this.loading.set(false);
        if (err?.status === 403) this.forbidden.set(true); else this.loadError.set(true);
      },
    });
  }

  onSubmit(): void {
    if (!this.canVote()) return;
    this.formSubmitted = true;
    if (this.form.invalid || !this.voteComplete()) {
      this.form.markAllAsTouched();
      const target = !this.voteComplete() ? 'overall-REAL' : 'expert-review-detail-justification';
      document.getElementById(target)?.focus();
      return;
    }
    const claimId = this.route.snapshot.paramMap.get('id');
    if (!claimId) return;
    this.voting.set(true);
    this.voteError.set('');

    const structured = this.isStructuredType();
    this.expertSvc.submitVote(claimId, {
      overall_verdict: this.selectedOverall()!,
      source_status: structured ? this.selectedSource() : null,
      content_status: structured && this.needsContentAndDate() ? this.selectedContent() : null,
      date_status: structured && this.needsContentAndDate() ? this.selectedDate() : null,
      justification: this.form.value.justification as string,
    }).subscribe({
      next: () => {
        this.submitted.set(true);
        this.voting.set(false);
        this.toast.success(this.isAdminDecision() ? 'Final decision recorded.' : 'Vote submitted.');
      },
      error: err => { this.voting.set(false); this.voteError.set(requestError(err, 'Your vote could not be submitted. Please try again.')); },
    });
  }
}
