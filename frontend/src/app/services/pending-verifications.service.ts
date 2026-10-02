import { Injectable, computed, inject, signal } from '@angular/core';
import { VerificationService } from './verification.service';
import { ToastService } from '../shared/services/toast.service';
import { SubmissionStatus, SubmissionType } from '../models/verification.model';

/**
 * Keeps track of verifications that are still running.
 *
 * A source-based verification takes up to a minute, which is far too long to
 * pin someone to the submit form. Claims are queued on the server and tracked
 * here instead, so the user can move around the app — or close the tab and
 * come back — and still be told when a verdict is ready.
 *
 * The list is mirrored into localStorage because the work outlives the page:
 * the pipeline keeps running on the server regardless of what the browser is
 * showing.
 */

const STORAGE_KEY = 'bfg.pending_verifications';
const POLL_INTERVAL_MS = 4000;
/** Stop chasing a job that is clearly never going to report back. */
const MAX_POLL_MS = 10 * 60 * 1000;

export interface TrackedVerification {
  submissionId: string;
  headline: string;
  source: string;
  /** Photo cards have no headline until the server has extracted it. */
  kind?: SubmissionType;
  status: SubmissionStatus;
  queuedAt: number;
  /** Set once the verdict is in, so the UI can offer a link to it. */
  done: boolean;
}

@Injectable({ providedIn: 'root' })
export class PendingVerificationsService {
  private readonly svc = inject(VerificationService);
  private readonly toast = inject(ToastService);

  private readonly items = signal<TrackedVerification[]>(this.restore());
  private timer: ReturnType<typeof setInterval> | null = null;

  /** Everything still being worked on. */
  readonly running = computed(() => this.items().filter((i) => !i.done));
  /** Finished, but not yet acknowledged by the user. */
  readonly ready = computed(() => this.items().filter((i) => i.done));
  readonly all = this.items.asReadonly();

  constructor() {
    if (this.running().length) this.ensurePolling();
  }

  /** Begin following a queued verification. */
  track(submissionId: string, headline: string, source: string, kind: SubmissionType = 'SOURCE_BASED'): void {
    if (this.items().some((i) => i.submissionId === submissionId)) return;
    this.items.update((list) => [
      { submissionId, headline, source, kind, status: 'PENDING', queuedAt: Date.now(), done: false },
      ...list,
    ]);
    this.persist();
    this.ensurePolling();
  }

  /** Drop a finished entry once the user has seen it. */
  dismiss(submissionId: string): void {
    this.items.update((list) => list.filter((i) => i.submissionId !== submissionId));
    this.persist();
  }

  clearFinished(): void {
    this.items.update((list) => list.filter((i) => !i.done));
    this.persist();
  }

  private ensurePolling(): void {
    if (this.timer !== null) return;
    this.timer = setInterval(() => this.poll(), POLL_INTERVAL_MS);
  }

  private stopPolling(): void {
    if (this.timer === null) return;
    clearInterval(this.timer);
    this.timer = null;
  }

  private poll(): void {
    const outstanding = this.running();
    if (!outstanding.length) {
      this.stopPolling();
      return;
    }
    // No need to chase a job while nobody is looking at the tab: it keeps
    // running on the server and is read back by id whenever the user returns.
    if (typeof document !== 'undefined' && document.hidden) return;

    for (const item of outstanding) {
      if (Date.now() - item.queuedAt > MAX_POLL_MS) {
        this.settle(item.submissionId, 'FAILED');
        continue;
      }

      this.svc.getStatus(item.submissionId).subscribe({
        next: (res) => {
          if (res.status === 'EXPERT_REVIEW' || res.status === 'FINALIZED') {
            this.settle(item.submissionId, res.status);
            this.toast.success(`Verification ready: ${this.short(item.headline)}`);
          } else if (res.status === 'FAILED') {
            this.settle(item.submissionId, 'FAILED');
            this.toast.error('A verification could not be completed. Open its result to try again; no verdict was reached.');
          } else {
            this.updateStatus(item.submissionId, res.status);
          }
        },
        // A single failed poll is not meaningful — the next tick retries.
        error: () => undefined,
      });
    }
  }

  private settle(submissionId: string, status: SubmissionStatus): void {
    this.items.update((list) =>
      list.map((i) => (i.submissionId === submissionId ? { ...i, status, done: true } : i)),
    );
    this.persist();
    if (!this.running().length) this.stopPolling();
  }

  private updateStatus(submissionId: string, status: SubmissionStatus): void {
    this.items.update((list) =>
      list.map((i) => (i.submissionId === submissionId ? { ...i, status } : i)),
    );
    this.persist();
  }

  private short(headline: string): string {
    return headline.length > 42 ? `${headline.slice(0, 42)}…` : headline;
  }

  private persist(): void {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(this.items()));
    } catch {
      // Private-mode or a full quota: tracking is a convenience, not state
      // the result depends on, so carry on without it.
    }
  }

  private restore(): TrackedVerification[] {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return [];
      const parsed = JSON.parse(raw) as TrackedVerification[];
      if (!Array.isArray(parsed)) return [];
      // Anything older than the poll ceiling is stale from a previous visit.
      return parsed.filter((i) => Date.now() - i.queuedAt < MAX_POLL_MS);
    } catch {
      return [];
    }
  }
}
