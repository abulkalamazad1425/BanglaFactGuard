import { Component, OnDestroy, OnInit, computed, inject, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { CommonModule } from '@angular/common';
import { VerificationService, MultimodalService } from '../../../services/verification.service';
import { SubmissionsService } from '../../../services/submissions.service';
import { PhotoCardService } from '../../../services/photocard.service';
import {
  MultimodalPredictionDetail,
  SubmissionLookup,
  VerificationResponse,
} from '../../../models/verification.model';
import { PhotoCardResultResponse } from '../../../models/photocard.model';
import { VerificationReportComponent } from '../../../shared/components/verification-report/verification-report.component';

/**
 * Universal submission result page — the one destination every "view this
 * claim" link in the app points to (Fact Explorer rows, submission history,
 * notification links), regardless of which of the three verification
 * methods produced it.
 *
 * The three methods are not interchangeable: each has its own detail
 * endpoint and its own shape (a source-based claim has a matched article
 * and a 3-part verdict; a multimodal check has an uploaded image and a
 * binary FAKE/REAL call; a photo card has both OCR text and a source
 * verdict). Rather than forcing one of those shapes to stand in for all
 * three, this component looks up the submission's type first and then
 * renders a layout built for that type specifically.
 */
@Component({
  selector: 'app-verify-result',
  standalone: true,
  imports: [CommonModule, RouterLink, VerificationReportComponent],
  templateUrl: './verify-result.html',
  styleUrls: ['./verify-result.scss']
})
export class VerifyResultComponent implements OnInit, OnDestroy {
  private readonly route = inject(ActivatedRoute);
  private readonly verificationSvc = inject(VerificationService);
  private readonly multimodalSvc = inject(MultimodalService);
  private readonly photocardSvc = inject(PhotoCardService);
  private readonly submissionsSvc = inject(SubmissionsService);

  readonly loading = signal(true);
  readonly lookup = signal<SubmissionLookup | null>(null);
  readonly notFound = signal(false);

  readonly sourceResult = signal<VerificationResponse | null>(null);
  readonly photocardResult = signal<PhotoCardResultResponse | null>(null);
  readonly multimodalResult = signal<MultimodalPredictionDetail | null>(null);

  copied = false;
  submissionId: string | null = null;

  private pollTimer: ReturnType<typeof setInterval> | null = null;

  readonly kind = computed(() => this.lookup()?.submission_type ?? null);

  /** True once the pipeline has produced a verdict to show, for whichever
   *  type this submission is. */
  readonly hasDetail = computed(
    () => !!(this.sourceResult() || this.photocardResult() || this.multimodalResult()),
  );

  /** True while the pipeline is still working — multimodal never sits here,
   *  it finalises synchronously within the request that created it. */
  readonly stillRunning = computed(() => {
    const s = this.photocardResult()?.status ?? this.lookup()?.status;
    return s === 'PENDING' || s === 'PROCESSING';
  });

  readonly failed = computed(
    () => (this.photocardResult()?.status ?? this.lookup()?.status) === 'FAILED',
  );

  /** Why a failed submission failed, in words the submitter can act on. */
  readonly failureReason = computed(
    () => this.photocardResult()?.failure_reason ?? this.lookup()?.failure_reason ?? null,
  );

  /** Server-side phase of a pending photo card, for the progress text. */
  readonly phaseText = computed(() => {
    const phase = this.photocardResult()?.phase ?? this.lookup()?.processing_phase;
    switch (phase) {
      case 'QUEUED': return 'Waiting for a worker';
      case 'EXTRACTING': return 'Reading the card and extracting its headline';
      case 'VERIFYING': return 'Checking the headline against the claimed source';
      default: return 'Working';
    }
  });

  shareUrl = () => `${window.location.origin}/verify/${this.submissionId}`;

  ngOnInit(): void {
    const id = this.route.snapshot.paramMap.get('id');
    if (!id) { this.loading.set(false); this.notFound.set(true); return; }
    this.submissionId = id;
    this.load(id);
  }

  ngOnDestroy(): void {
    this.stopPolling();
  }

  /**
   * Results are produced in the background (source-based and photo-card both
   * go through the same async pipeline), so this page is routinely opened
   * while work is still in progress — poll the type-agnostic lookup until a
   * verdict exists, then fetch the one detail endpoint that actually applies.
   */
  private load(id: string): void {
    this.submissionsSvc.getLookup(id).subscribe({
      next: (l) => {
        this.lookup.set(l);

        if (l.submission_type === 'PHOTO_CARD') {
          // A photo card is readable in EVERY state (pending, processing,
          // failed, complete): the detail endpoint returns the stored image,
          // the extracted headline once known, a failure reason, or the saved
          // result - so the page never needs the extracted headline to exist.
          this.loadPhotocard(id);
          return;
        }

        if (l.status === 'EXPERT_REVIEW' || l.status === 'FINALIZED' || l.status === 'ESCALATED') {
          this.stopPolling();
          this.loadDetail(id, l.submission_type);
        } else if (l.status === 'FAILED') {
          this.stopPolling();
          this.loading.set(false);
        } else {
          this.loading.set(false);
          this.ensurePolling(id);
        }
      },
      error: () => {
        this.stopPolling();
        this.loading.set(false);
        this.notFound.set(true);
      },
    });
  }

  private loadPhotocard(id: string): void {
    this.photocardSvc.getResult(id).subscribe({
      next: (r) => {
        this.photocardResult.set(r);
        this.loading.set(false);
        if (r.status === 'PENDING' || r.status === 'PROCESSING') {
          this.ensurePolling(id);
        } else {
          this.stopPolling();
        }
      },
      error: () => {
        this.stopPolling();
        this.loading.set(false);
        this.notFound.set(true);
      },
    });
  }

  private loadDetail(id: string, kind: SubmissionLookup['submission_type']): void {
    if (kind === 'SOURCE_BASED') {
      this.verificationSvc.getResult(id).subscribe({
        next: (r) => { this.sourceResult.set(r); this.loading.set(false); },
        error: () => this.loading.set(false),
      });
    } else if (kind === 'PHOTO_CARD') {
      this.photocardSvc.getResult(id).subscribe({
        next: (r) => { this.photocardResult.set(r); this.loading.set(false); },
        error: () => this.loading.set(false),
      });
    } else {
      this.multimodalSvc.getBySubmission(id).subscribe({
        next: (r) => { this.multimodalResult.set(r); this.loading.set(false); },
        error: () => this.loading.set(false),
      });
    }
  }

  private ensurePolling(id: string): void {
    if (this.pollTimer !== null) return;
    // Polling is only a courtesy to a viewer who stays: it pauses while the
    // tab is hidden and stops entirely when the page is left (ngOnDestroy).
    // None of that affects the server-side job.
    this.pollTimer = setInterval(() => {
      if (typeof document !== 'undefined' && document.hidden) return;
      this.load(id);
    }, 4000);
  }

  private stopPolling(): void {
    if (this.pollTimer === null) return;
    clearInterval(this.pollTimer);
    this.pollTimer = null;
  }

  /* ─── Shared template helpers ─── */

  /** Lifecycle states in which a saved automated result exists. */
  isReviewed(status: string | undefined): boolean {
    return status === 'EXPERT_REVIEW' || status === 'FINALIZED' || status === 'ESCALATED';
  }

  /** Ring/accent colour for a source-based or photo-card verdict —
   *  content status wins once the source is confirmed; a date mismatch
   *  never changes this colour. */
  verdictColor(v: VerificationResponse | null): string {
    if (!v || v.source_status === 'NOT_FOUND') return '#6b7280';
    if (v.content_status === 'MATCHED') return '#10b981';
    if (v.content_status === 'ALTERED') return '#f59e0b';
    return '#6b7280';
  }

  getDashOffset(confidence: number): number {
    return 283 - 283 * (confidence || 0);
  }

  /** The binary multimodal model can only imply FAKE/REAL — true if the
   *  expert-finalized verdict is something else, or flips that call. */
  multimodalWasOverridden(m: MultimodalPredictionDetail): boolean {
    if (!m.expert_overall_verdict) return false;
    const impliedByAi = m.prediction === 'FAKE' ? 'FAKE' : 'REAL';
    return m.expert_overall_verdict !== impliedByAi;
  }

  overallVerdictLabel(v: string): string {
    const labels: Record<string, string> = {
      FAKE: 'Fake',
      REAL: 'Real',
      MISLEADING: 'Misleading',
      ALTERED: 'Altered',
    };
    return labels[v] ?? v;
  }

  getHost(url: string): string {
    try {
      return new URL(url).hostname.replace('www.', '');
    } catch {
      return '';
    }
  }

  copyUrl(): void {
    navigator.clipboard.writeText(this.shareUrl());
    this.copied = true;
    setTimeout(() => this.copied = false, 2000);
  }
}
