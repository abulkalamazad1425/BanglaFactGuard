import { Component, OnInit, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { ExpertService } from '../../../services/expert.service';
import { ExpertHistoryItem } from '../../../models/expert.model';
import { VerdictBadgeComponent } from '../../../shared/components/verdict-badge/verdict-badge.component';
import { DATE_LABELS, SOURCE_LABELS, SOURCE_QUESTION } from '../../../shared/utils/status-labels';

@Component({
  selector: 'app-expert-history',
  standalone: true,
  imports: [CommonModule, RouterLink, VerdictBadgeComponent],
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
  readonly limit = 20;
  readonly page = () => Math.floor(this.offset() / this.limit) + 1;
  search(value: string): void {
    this.query = value.trim();
    this.offset.set(0);
    this.load();
  }
  prev(): void {
    this.offset.update((o) => Math.max(0, o - this.limit));
    this.load();
  }
  next(): void {
    this.offset.update((o) => o + this.limit);
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
  load(): void {
    this.loading.set(true);
    this.expertSvc.getHistory(this.limit, this.offset(), this.query).subscribe({
      next: (h) => {
        this.history.set(h);
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
