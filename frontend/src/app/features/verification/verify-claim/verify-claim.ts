import { requestError } from '../../../shared/utils/presentation';
import { Component, OnDestroy, OnInit, inject } from '@angular/core';
import {
  AbstractControl,
  FormBuilder,
  ReactiveFormsModule,
  ValidationErrors,
  Validators,
} from '@angular/forms';

/** Like minLength, but whitespace never counts (the API strips it). */
export function trimmedMinLength(min: number) {
  return (c: AbstractControl): ValidationErrors | null =>
    String(c.value ?? '').trim().length >= min ? null : { trimmedMinLength: { min } };
}
import { Router, RouterLink } from '@angular/router';
import { CommonModule } from '@angular/common';
import { ToastService } from '../../../shared/services/toast.service';
import { AuthService } from '../../../services/auth.service';
import { verificationFollowUp } from '../../../shared/utils/status-labels';
import { VerificationService } from '../../../services/verification.service';
import { PendingVerificationsService } from '../../../services/pending-verifications.service';
import {
  ContentStatus,
  SourceStatus,
  SubmissionStatus,
  VerificationResponse,
} from '../../../models/verification.model';
import { VerificationReportComponent } from '../../../shared/components/verification-report/verification-report.component';
import { SourceService } from '../../../services/source.service';
import { SourceResponse } from '../../../models/source.model';

@Component({
  selector: 'app-verify-claim',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, RouterLink, VerificationReportComponent],
  templateUrl: './verify-claim.html',
  styleUrls: ['./verify-claim.scss'],
})
export class VerifyClaimComponent implements OnInit, OnDestroy {
  private readonly fb = inject(FormBuilder);
  private readonly router = inject(Router);
  private readonly toast = inject(ToastService);
  private readonly svc = inject(VerificationService);
  private readonly sourceSvc = inject(SourceService);
  readonly pending = inject(PendingVerificationsService);
  /** Signed-in and anonymous users are told different next steps. */
  readonly signedIn = inject(AuthService).isLoggedIn;
  readonly followUp = verificationFollowUp;

  loading = false;
  error: string | null = null;
  result: VerificationResponse | null = null;

  /** Set when this particular result was reused rather than freshly computed. */
  servedFromCache = false;
  /** Id of the claim currently being verified, while we wait on it. */
  pendingSubmissionId: string | null = null;
  pendingStatus: SubmissionStatus | null = null;
  pendingHeadline = '';
  lastSubmissionId: string | null = null;
  resultLoadError = false;

  sources: SourceResponse[] = [];
  sourcesLoading = true;
  sourcesError = false;

  private pollTimer: ReturnType<typeof setInterval> | null = null;

  form = this.fb.group({
    // Same rules as the API (VerificationRequest): headline >= 5 non-blank
    // characters; claimed outlet, article text and date optional. Without an
    // outlet the claim is checked against the active verified sources.
    headline: ['', [Validators.required, trimmedMinLength(5), Validators.maxLength(2000)]],
    claimed_source_text: [''],
    body_text: [''],
    published_date: [''],
  });

  ngOnInit(): void {
    this.loadSources();
  }

  loadSources(): void {
    this.sourcesLoading = true;
    this.sourcesError = false;
    // Only active verified sources are ever eligible for selection here.
    this.sourceSvc.listSources(undefined, 1, 100).subscribe({
      next: (res) => {
        this.sources = [...res.items].sort((a, b) =>
          a.display_name.localeCompare(b.display_name, 'bn'),
        );
        this.sourcesLoading = false;
      },
      error: () => {
        this.sourcesLoading = false;
        this.sourcesError = true;
      },
    });
  }

  get headlineInvalid() {
    return this.form.get('headline')?.invalid && this.form.get('headline')?.touched;
  }

  get sourceInvalid() {
    return (
      this.form.get('claimed_source_text')?.invalid && this.form.get('claimed_source_text')?.touched
    );
  }

  onSubmit(): void {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      document.getElementById('verify-claim-headline')?.focus();
      return;
    }

    this.loading = true;
    this.error = null;
    this.result = null;
    this.servedFromCache = false;
    this.resultLoadError = false;

    const v = this.form.value;
    const payload: any = { headline: v.headline };
    if (v.claimed_source_text?.trim()) payload.claimed_source_text = v.claimed_source_text;
    if (v.body_text?.trim()) payload.body_text = v.body_text;
    if (v.published_date) payload.published_date = v.published_date;

    this.pendingHeadline = v.headline ?? '';

    this.svc.submitAsync(payload).subscribe({
      next: (queued) => {
        this.lastSubmissionId = queued.submission_id;
        this.loading = false;
        this.pendingSubmissionId = queued.submission_id;
        this.pendingStatus = queued.status;

        if (queued.cached) {
          // Already verified before — the stored verdict is available now.
          this.servedFromCache = true;
          this.loadResult(queued.submission_id);
          return;
        }

        // Registered and running on the server. Follow it here for anyone who
        // stays, and hand it to the tracker so leaving the page is safe.
        this.pending.track(queued.submission_id, this.pendingHeadline, v.claimed_source_text ?? '');
        this.startPolling(queued.submission_id);
      },
      error: (err) => {
        this.loading = false;
        this.pendingSubmissionId = null;
        this.error = requestError(err, 'Unable to submit your claim. Please try again.');
        this.toast.error(this.error!);
      },
    });
  }

  /** Watch a queued verification while the user is still on this page. */
  private startPolling(submissionId: string): void {
    this.stopPolling();
    this.pollTimer = setInterval(() => {
      this.svc.getStatus(submissionId).subscribe({
        next: (res) => {
          this.pendingStatus = res.status;
          if (
            res.status === 'EXPERT_REVIEW' ||
            res.status === 'FINALIZED' ||
            res.status === 'ESCALATED'
          ) {
            this.stopPolling();
            if (res.result) {
              this.result = res.result;
              this.pendingSubmissionId = null;
            } else {
              this.loadResult(submissionId);
            }
            this.pending.dismiss(submissionId);
          } else if (res.status === 'FAILED') {
            this.stopPolling();
            this.pendingSubmissionId = null;
            this.error =
              'Verification could not be completed. Please try again. No verdict was reached.';
            this.pending.dismiss(submissionId);
          }
        },
        // Transient poll failures resolve themselves on the next tick.
        error: () => undefined,
      });
    }, 4000);
  }

  private stopPolling(): void {
    if (this.pollTimer === null) return;
    clearInterval(this.pollTimer);
    this.pollTimer = null;
  }

  private loadResult(submissionId: string): void {
    this.svc.getResult(submissionId).subscribe({
      next: (result) => {
        this.result = result;
        this.pendingSubmissionId = null;
      },
      error: () => {
        this.pendingSubmissionId = null;
        this.resultLoadError = true;
        this.error =
          'Your claim was received, but the saved result could not be loaded. Open its report to try again.';
      },
    });
  }

  ngOnDestroy(): void {
    // The tracker keeps following it app-wide; this page just stops its own.
    this.stopPolling();
  }

  reset(): void {
    this.error = null;
    this.result = null;
    this.servedFromCache = false;
    this.pendingSubmissionId = null;
    this.pendingStatus = null;
    this.stopPolling();
  }

  /* ─── Template helpers ─── */

  /** Ring/accent colour for the overall verdict — content status wins once
   *  the source is confirmed; a date mismatch never changes this colour. */
  verdictColor(
    sourceStatus: SourceStatus | null | undefined,
    contentStatus?: ContentStatus | null,
  ): string {
    if (sourceStatus === 'NOT_FOUND') return '#6b7280';
    if (contentStatus === 'MATCHED') return '#10b981';
    if (contentStatus === 'ALTERED') return '#f59e0b';
    return '#6b7280';
  }

  getDashOffset(confidence: number): number {
    // Circumference of r=45 circle ≈ 282.7
    return 283 - 283 * (confidence || 0);
  }

  getHost(url: string): string {
    try {
      return new URL(url).hostname.replace('www.', '');
    } catch {
      return '';
    }
  }
}
