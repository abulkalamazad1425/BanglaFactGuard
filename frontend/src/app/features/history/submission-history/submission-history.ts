import { Component, OnDestroy, OnInit, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { VerificationService } from '../../../services/verification.service';
import { SubmissionSummary, SubmissionStats } from '../../../models/verification.model';
import { VerdictBadgeComponent } from '../../../shared/components/verdict-badge/verdict-badge.component';
import { STRENGTH_HELP } from '../../../shared/utils/result-view';

/**
 * My Submissions. Rows exist from the moment a submission is accepted —
 * including a photo card whose headline has not been extracted yet — and are
 * readable in every state (pending, processing, failed, complete). Only the
 * signed-in user's own submissions are listed (owner-only on the server).
 *
 * While any row is still pending/processing the list refreshes itself, but
 * only while this page is open and the tab is visible; leaving the page stops
 * the refresh and never affects the server-side jobs.
 */
@Component({
  selector: 'app-submission-history',
  standalone: true,
  imports: [CommonModule, RouterLink, VerdictBadgeComponent],
  templateUrl: './submission-history.html',
  styleUrls: ['./submission-history.scss']
})
export class SubmissionHistoryComponent implements OnInit, OnDestroy {
  private readonly verificationSvc = inject(VerificationService);

  readonly loading = signal(true);
  readonly submissions = signal<SubmissionSummary[]>([]);
  readonly stats = signal<SubmissionStats | null>(null);
  readonly offset = signal(0);
  readonly limit = 20;
  readonly strengthHelp = STRENGTH_HELP;

  private refreshTimer: ReturnType<typeof setInterval> | null = null;

  readonly page = () => Math.floor(this.offset() / this.limit) + 1;

  ngOnInit(): void {
    this.refreshStats();
    this.load();
  }

  ngOnDestroy(): void {
    this.stopRefresh();
  }

  private refreshStats(): void {
    this.verificationSvc.getMyStats().subscribe({
      next: s => this.stats.set(s), error: () => { }
    });
  }

  load(silent = false): void {
    if (!silent) this.loading.set(true);
    this.verificationSvc.getMySubmissions(this.limit, this.offset())
      .subscribe({
        next: s => {
          this.submissions.set(s);
          this.loading.set(false);
          if (s.some(x => this.isRunning(x))) this.ensureRefresh(); else this.stopRefresh();
        },
        error: () => this.loading.set(false),
      });
  }

  private ensureRefresh(): void {
    if (this.refreshTimer !== null) return;
    this.refreshTimer = setInterval(() => {
      if (typeof document !== 'undefined' && document.hidden) return;
      this.load(true);
      this.refreshStats();
    }, 6000);
  }

  private stopRefresh(): void {
    if (this.refreshTimer === null) return;
    clearInterval(this.refreshTimer);
    this.refreshTimer = null;
  }

  prev(): void { this.offset.update(o => Math.max(0, o - this.limit)); this.load(); }
  next(): void { this.offset.update(o => o + this.limit); this.load(); }

  /* ─── Row state helpers ─── */

  isRunning(s: SubmissionSummary): boolean {
    return s.status === 'PENDING' || s.status === 'PROCESSING';
  }

  isFailed(s: SubmissionSummary): boolean {
    return s.status === 'FAILED';
  }

  hasResult(s: SubmissionSummary): boolean {
    return !this.isRunning(s) && !this.isFailed(s) && s.source_status !== null;
  }

  typeLabel(t: string): string {
    return t === 'PHOTO_CARD' ? '🖼️ Photo card' : t === 'MULTIMODAL' ? '🧠 Multimodal' : '🔎 Text claim';
  }

  /** What to show where the headline would be — a pending photo card has none yet. */
  headlineText(s: SubmissionSummary): string {
    if (s.headline) return s.headline;
    if (s.submission_type === 'PHOTO_CARD') {
      return this.isFailed(s) ? '(no headline could be read)' : 'Reading headline from the card…';
    }
    return '(no headline recorded)';
  }

  phaseText(s: SubmissionSummary): string {
    switch (s.phase) {
      case 'EXTRACTING': return 'Reading the card';
      case 'VERIFYING': return 'Checking the source';
      case 'QUEUED': return 'Queued';
      default: return s.status === 'PENDING' ? 'Queued' : 'In progress';
    }
  }

  truncate(text: string, n: number): string {
    return text.length > n ? text.slice(0, n) + '…' : text;
  }
}
