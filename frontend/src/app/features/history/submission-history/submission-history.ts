import { Component, OnDestroy, OnInit, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { Subscription } from 'rxjs';
import { VerificationService } from '../../../services/verification.service';
import {
  MySubmissionState,
  SubmissionStats,
  SubmissionSummary,
  SubmissionType,
} from '../../../models/verification.model';
import { VerdictBadgeComponent } from '../../../shared/components/verdict-badge/verdict-badge.component';
import {
  PAGE_SIZE,
  PaginationComponent,
} from '../../../shared/components/pagination/pagination.component';

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
  imports: [CommonModule, RouterLink, VerdictBadgeComponent, PaginationComponent],
  templateUrl: './submission-history.html',
  styleUrls: ['./submission-history.scss'],
})
export class SubmissionHistoryComponent implements OnInit, OnDestroy {
  private readonly verificationSvc = inject(VerificationService);

  readonly loading = signal(true);
  readonly loadError = signal(false);
  readonly submissions = signal<SubmissionSummary[]>([]);
  readonly stats = signal<SubmissionStats | null>(null);
  readonly offset = signal(0);
  readonly limit = PAGE_SIZE;
  readonly hasNext = signal(false);

  /* ─── Search & filters (applied on the server, before pagination) ─── */
  query = '';
  readonly state = signal<MySubmissionState | ''>('');
  readonly type = signal<SubmissionType | ''>('');
  readonly states: { key: MySubmissionState | ''; label: string }[] = [
    { key: '', label: 'All statuses' },
    { key: 'in_progress', label: 'In progress' },
    { key: 'review', label: 'Under expert review' },
    { key: 'final', label: 'Final decision' },
    { key: 'failed', label: 'Check incomplete' },
  ];
  readonly types: { key: SubmissionType | ''; label: string }[] = [
    { key: '', label: 'All types' },
    { key: 'SOURCE_BASED', label: 'Text & source' },
    { key: 'PHOTO_CARD', label: 'Photo card' },
    { key: 'MULTIMODAL', label: 'Text & image' },
  ];
  readonly filtered = () => Boolean(this.query || this.state() || this.type());
  private searchTimer: ReturnType<typeof setTimeout> | null = null;
  private request?: Subscription;

  private refreshTimer: ReturnType<typeof setInterval> | null = null;

  readonly page = () => Math.floor(this.offset() / this.limit) + 1;

  ngOnInit(): void {
    this.refreshStats();
    this.load();
  }

  ngOnDestroy(): void {
    if (this.searchTimer) clearTimeout(this.searchTimer);
    this.request?.unsubscribe();
    this.stopRefresh();
  }

  private refreshStats(): void {
    this.verificationSvc.getMyStats().subscribe({
      next: (s) => this.stats.set(s),
      error: () => {},
    });
  }

  search(value: string): void {
    if (this.searchTimer) clearTimeout(this.searchTimer);
    this.query = value.trim();
    this.offset.set(0);
    this.load();
  }

  /** Search as you type: ~300 ms after the last keystroke, first page. */
  onSearchInput(value: string): void {
    if (this.searchTimer) clearTimeout(this.searchTimer);
    this.searchTimer = setTimeout(() => {
      this.searchTimer = null;
      if (value.trim() !== this.query) this.search(value);
    }, 300);
  }

  setState(value: string): void {
    this.state.set(value as MySubmissionState | '');
    this.offset.set(0);
    this.load();
  }

  setType(value: string): void {
    this.type.set(value as SubmissionType | '');
    this.offset.set(0);
    this.load();
  }

  clearFilters(input: HTMLInputElement): void {
    input.value = '';
    this.query = '';
    this.state.set('');
    this.type.set('');
    this.offset.set(0);
    this.load();
  }

  load(silent = false): void {
    if (!silent) this.loading.set(true);
    // A newer search or filter supersedes any request still in flight.
    this.request?.unsubscribe();
    // One extra row tells whether another page exists.
    this.request = this.verificationSvc
      .getMySubmissions(this.limit + 1, this.offset(), {
        q: this.query,
        state: this.state(),
        type: this.type(),
      })
      .subscribe({
        next: (rows) => {
          const s = rows.slice(0, this.limit);
          this.hasNext.set(rows.length > this.limit);
          this.submissions.set(s);
          this.loading.set(false);
          this.loadError.set(false);
          if (s.some((x) => !x.is_finalized && !this.isFailed(x))) this.ensureRefresh();
          else this.stopRefresh();
        },
        error: () => {
          this.loading.set(false);
          this.loadError.set(true);
        },
      });
  }

  private ensureRefresh(): void {
    if (this.refreshTimer !== null) return;
    this.refreshTimer = setInterval(() => {
      if (typeof document !== 'undefined' && document.hidden) return;
      this.load(true);
      this.refreshStats();
    }, 15000);
  }

  private stopRefresh(): void {
    if (this.refreshTimer === null) return;
    clearInterval(this.refreshTimer);
    this.refreshTimer = null;
  }

  goToPage(page: number): void {
    this.offset.set((page - 1) * this.limit);
    this.load();
  }

  /* ─── Row state helpers ─── */

  isRunning(s: SubmissionSummary): boolean {
    return s.status === 'PENDING' || s.status === 'PROCESSING';
  }

  isFailed(s: SubmissionSummary): boolean {
    return s.status === 'FAILED';
  }

  hasResult(s: SubmissionSummary): boolean {
    return (
      !this.isRunning(s) &&
      !this.isFailed(s) &&
      Boolean(s.source_status || s.prediction || s.overall_verdict)
    );
  }

  typeLabel(t: string): string {
    return t === 'PHOTO_CARD'
      ? 'Photo card'
      : t === 'MULTIMODAL'
        ? 'Text & image'
        : 'Text & source';
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
      case 'EXTRACTING':
        return 'Reading the card';
      case 'VERIFYING':
        return 'Checking the source';
      case 'QUEUED':
        return 'Queued';
      default:
        return s.status === 'PENDING' ? 'Queued' : 'In progress';
    }
  }

  truncate(text: string, n: number): string {
    return text.length > n ? text.slice(0, n) + '…' : text;
  }
}
