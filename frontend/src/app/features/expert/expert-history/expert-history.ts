import { Component, OnInit, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { Subscription } from 'rxjs';
import { ExpertService } from '../../../services/expert.service';
import { ExpertHistoryItem } from '../../../models/expert.model';
import { VerdictBadgeComponent } from '../../../shared/components/verdict-badge/verdict-badge.component';
import {
  PAGE_SIZE,
  PaginationComponent,
} from '../../../shared/components/pagination/pagination.component';
import { DATE_LABELS, SOURCE_LABELS, SOURCE_QUESTION } from '../../../shared/utils/status-labels';

@Component({
  selector: 'app-expert-history',
  standalone: true,
  imports: [CommonModule, RouterLink, VerdictBadgeComponent, PaginationComponent],
  templateUrl: './expert-history.html',
  styleUrls: ['./expert-history.scss'],
})
export class ExpertHistoryComponent implements OnInit {
  private readonly expertSvc = inject(ExpertService);

  readonly loading = signal(true);
  readonly loadError = signal(false);
  readonly history = signal<ExpertHistoryItem[]>([]);

  query = '';
  readonly offset = signal(0);
  readonly limit = PAGE_SIZE;
  readonly hasNext = signal(false);
  readonly page = () => Math.floor(this.offset() / this.limit) + 1;
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
  goToPage(page: number): void {
    this.offset.set((page - 1) * this.limit);
    this.load();
  }
  ngOnInit(): void {
    this.load();
  }
  /** The optional, non-decisive findings recorded with a vote, as plain text. */
  supplementary(h: ExpertHistoryItem): string {
    if (!h.vote_source_status) return 'None recorded.';
    const parts = [`${SOURCE_QUESTION}: ${SOURCE_LABELS[h.vote_source_status]}`];
    if (h.vote_content_status)
      parts.push(`Headline: ${h.vote_content_status === 'ALTERED' ? 'Altered' : 'Matched'}`);
    if (h.vote_date_status) parts.push(`Date: ${DATE_LABELS[h.vote_date_status]}`);
    return parts.join(' · ');
  }
  private request?: Subscription;

  load(): void {
    this.request?.unsubscribe();
    this.loading.set(true);
    // One extra row tells whether another page exists.
    this.request = this.expertSvc.getHistory(this.limit + 1, this.offset(), this.query).subscribe({
      next: (rows) => {
        this.hasNext.set(rows.length > this.limit);
        this.history.set(rows.slice(0, this.limit));
        this.loading.set(false);
        this.loadError.set(false);
      },
      error: () => {
        this.loading.set(false);
        this.loadError.set(true);
      },
    });
  }
}
