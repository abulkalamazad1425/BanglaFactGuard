import { Component, DestroyRef, OnInit, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { Subscription } from 'rxjs';
import { ExpertService } from '../../../services/expert.service';
import { ExpertQueueItem } from '../../../models/expert.model';
import { VerdictBadgeComponent } from '../../../shared/components/verdict-badge/verdict-badge.component';
import { AuthService } from '../../../services/auth.service';
import {
  PAGE_SIZE,
  PaginationComponent,
} from '../../../shared/components/pagination/pagination.component';

type QueueState = 'all' | 'escalated' | 'review';

/**
 * The review queue. Experts see open claims awaiting their vote (never
 * escalated ones). Admins use the same page at /admin/review-queue: escalated
 * claims — theirs to decide — come first, and open claims are view-only.
 */
@Component({
  selector: 'app-expert-queue',
  standalone: true,
  imports: [CommonModule, RouterLink, VerdictBadgeComponent, PaginationComponent],
  templateUrl: './expert-queue.html',
  styleUrls: ['./expert-queue.scss'],
})
export class ExpertQueueComponent implements OnInit {
  private readonly expertSvc = inject(ExpertService);
  private readonly auth = inject(AuthService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly destroyRef = inject(DestroyRef);

  readonly isAdmin = this.auth.isAdmin;
  readonly loading = signal(true);
  readonly loadError = signal(false);
  readonly queue = signal<ExpertQueueItem[]>([]);
  readonly state = signal<QueueState>('all');
  readonly states: { key: QueueState; label: string }[] = [
    { key: 'all', label: 'All' },
    { key: 'escalated', label: 'Escalated — needs your decision' },
    { key: 'review', label: 'In expert review (view only)' },
  ];
  query = '';
  readonly offset = signal(0);
  readonly limit = PAGE_SIZE;
  readonly hasNext = signal(false);
  readonly page = () => Math.floor(this.offset() / this.limit) + 1;

  ngOnInit(): void {
    this.route.queryParamMap.pipe(takeUntilDestroyed(this.destroyRef)).subscribe((params) => {
      const s = params.get('state');
      this.state.set(this.isAdmin() && (s === 'escalated' || s === 'review') ? s : 'all');
      this.offset.set(0);
      this.load();
    });
  }

  search(value: string): void {
    if (this.searchTimer) clearTimeout(this.searchTimer);
    this.query = value.trim();
    this.offset.set(0);
    this.load();
  }

  /** Search as you type: ~300 ms after the last keystroke, first page. */
  private searchTimer: ReturnType<typeof setTimeout> | null = null;
  onSearchInput(value: string): void {
    if (this.searchTimer) clearTimeout(this.searchTimer);
    this.searchTimer = setTimeout(() => {
      this.searchTimer = null;
      if (value.trim() !== this.query) this.search(value);
    }, 300);
  }

  selectState(state: QueueState): void {
    this.router.navigate([], {
      relativeTo: this.route,
      queryParams: { state: state === 'all' ? null : state },
    });
  }

  private request?: Subscription;

  load(): void {
    // A newer search supersedes any request still in flight.
    this.request?.unsubscribe();
    this.loading.set(true);
    this.request = this.expertSvc
      // One extra row tells whether another page exists.
      .getQueue(this.limit + 1, this.offset(), this.query, this.isAdmin() ? this.state() : 'all')
      .subscribe({
        next: (rows) => {
          this.hasNext.set(rows.length > this.limit);
          this.queue.set(rows.slice(0, this.limit));
          this.loading.set(false);
          this.loadError.set(false);
        },
        error: () => {
          this.loading.set(false);
          this.loadError.set(true);
        },
      });
  }

  goToPage(page: number): void {
    this.offset.set((page - 1) * this.limit);
    this.load();
  }

  detailLink(item: ExpertQueueItem): string[] {
    return [this.isAdmin() ? '/admin/review-queue' : '/expert/queue', item.submission_id];
  }

  typeLabel(t: ExpertQueueItem['submission_type']): string {
    const labels: Record<string, string> = {
      SOURCE_BASED: 'Text & source',
      PHOTO_CARD: 'Photo card',
      MULTIMODAL: 'Text & image',
    };
    return labels[t] ?? 'News check';
  }
}
