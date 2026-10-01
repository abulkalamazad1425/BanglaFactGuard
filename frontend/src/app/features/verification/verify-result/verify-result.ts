import { Component, OnDestroy, OnInit, computed, inject, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { CommonModule } from '@angular/common';
import { VerificationService } from '../../../services/verification.service';
import { SubmissionStatus, VerificationResponse } from '../../../models/verification.model';
import { VerdictBadgeComponent } from '../../../shared/components/verdict-badge/verdict-badge.component';

@Component({
  selector: 'app-verify-result',
  standalone: true,
  imports: [CommonModule, RouterLink, VerdictBadgeComponent],
  templateUrl: './verify-result.html',
  styleUrls: ['./verify-result.scss']
})
export class VerifyResultComponent implements OnInit, OnDestroy {
  private readonly route = inject(ActivatedRoute);
  private readonly verificationSvc = inject(VerificationService);

  readonly loading = signal(true);
  readonly result = signal<VerificationResponse | null>(null);
  readonly status = signal<SubmissionStatus | null>(null);
  copied = false;
  submissionId: string | null = null;

  private pollTimer: ReturnType<typeof setInterval> | null = null;

  /** True while the pipeline is still working on this submission. */
  readonly stillRunning = computed(
    () => this.status() === 'PENDING' || this.status() === 'PROCESSING',
  );

  /** Ring/accent colour for the overall verdict — content status wins once
   *  the source is confirmed; a date mismatch never changes this colour. */
  verdictColor(): string {
    const r = this.result();
    if (!r || r.source_status === 'NOT_FOUND') return '#6b7280';
    if (r.content_status === 'MATCHED') return '#10b981';
    if (r.content_status === 'ALTERED') return '#f59e0b';
    return '#6b7280';
  }

  getDashOffset(confidence: number): number {
    return 283 - 283 * (confidence || 0);
  }

  getHost(url: string): string {
    try {
      return new URL(url).hostname.replace('www.', '');
    } catch {
      return '';
    }
  }

  shareUrl = () => `${window.location.origin}/verify/${this.result()?.submission_id}`;

  ngOnInit(): void {
    const id = this.route.snapshot.paramMap.get('id');
    if (!id) { this.loading.set(false); return; }
    this.submissionId = id;
    this.load(id);
  }

  /**
   * Results are produced in the background, so this page is routinely opened
   * while the pipeline is still running — poll until a verdict exists rather
   * than reporting the claim as missing.
   */
  private load(id: string): void {
    this.verificationSvc.getStatus(id).subscribe({
      next: (s) => {
        this.status.set(s.status);
        if (s.status === 'EXPERT_REVIEW' || s.status === 'FINALIZED') {
          this.stopPolling();
          if (s.result) {
            this.result.set(s.result);
            this.loading.set(false);
          } else {
            this.verificationSvc.getResult(id).subscribe({
              next: (r) => { this.result.set(r); this.loading.set(false); },
              error: () => this.loading.set(false),
            });
          }
        } else if (s.status === 'FAILED') {
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
      },
    });
  }

  private ensurePolling(id: string): void {
    if (this.pollTimer !== null) return;
    this.pollTimer = setInterval(() => this.load(id), 4000);
  }

  private stopPolling(): void {
    if (this.pollTimer === null) return;
    clearInterval(this.pollTimer);
    this.pollTimer = null;
  }

  ngOnDestroy(): void {
    this.stopPolling();
  }

  copyUrl(): void {
    navigator.clipboard.writeText(this.shareUrl());
    this.copied = true;
    setTimeout(() => this.copied = false, 2000);
  }
}
