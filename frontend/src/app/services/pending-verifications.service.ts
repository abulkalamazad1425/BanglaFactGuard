import { Injectable, computed, inject, signal } from '@angular/core';
import { VerificationService } from './verification.service';
import { ToastService } from '../shared/services/toast.service';
import { SubmissionStatus, SubmissionType } from '../models/verification.model';

const STORAGE_KEY = 'bfg.pending_verifications';

export function isDeletedOnServer(err: unknown, submissionId: string): boolean {
  const e = err as {
    status?: number;
    error?: { detail?: { error?: string; submission_id?: string } };
  } | null;
  const detail = e?.error?.detail;
  return (
    e?.status === 404 &&
    detail?.error === 'not_found' &&
    String(detail?.submission_id) === submissionId
  );
}
const POLL_INTERVAL_MS = 4000;
const MAX_POLL_MS = 10 * 60 * 1000;

export interface TrackedVerification {
  submissionId: string;
  headline: string;
  source: string;
  kind?: SubmissionType;
  status: SubmissionStatus;
  queuedAt: number;
  done: boolean;
}

@Injectable({ providedIn: 'root' })
export class PendingVerificationsService {
  private readonly svc = inject(VerificationService);
  private readonly toast = inject(ToastService);

  private readonly items = signal<TrackedVerification[]>(this.restore());
  private timer: ReturnType<typeof setInterval> | null = null;

  readonly running = computed(() => this.items().filter((i) => !i.done));
  readonly ready = computed(() => this.items().filter((i) => i.done));
  readonly all = this.items.asReadonly();

  constructor() {
    if (this.running().length) this.ensurePolling();
  }

  track(
    submissionId: string,
    headline: string,
    source: string,
    kind: SubmissionType = 'SOURCE_BASED',
  ): void {
    if (this.items().some((i) => i.submissionId === submissionId)) return;
    this.items.update((list) => [
      {
        submissionId,
        headline,
        source,
        kind,
        status: 'PENDING',
        queuedAt: Date.now(),
        done: false,
      },
      ...list,
    ]);
    this.persist();
    this.ensurePolling();
  }

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
            this.toast.error(
              'A verification could not be completed. Open its result to try again; no verdict was reached.',
            );
          } else {
            this.updateStatus(item.submissionId, res.status);
          }
        },
        error: (err) => {
          if (isDeletedOnServer(err, item.submissionId)) this.dismiss(item.submissionId);
        },
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
    }
  }

  private restore(): TrackedVerification[] {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return [];
      const parsed = JSON.parse(raw) as TrackedVerification[];
      if (!Array.isArray(parsed)) return [];
      return parsed.filter((i) => Date.now() - i.queuedAt < MAX_POLL_MS);
    } catch {
      return [];
    }
  }
}
