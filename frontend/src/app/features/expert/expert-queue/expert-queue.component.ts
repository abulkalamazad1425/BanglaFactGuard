import { Component, OnInit, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { ApiService } from '../../../core/services/api.service';
import { ExpertQueueItem } from '../../../core/models/expert.model';
import { VerdictBadgeComponent } from '../../../shared/components/verdict-badge/verdict-badge.component';
import { API_ENDPOINTS } from '../../../core/constants/api-endpoints.constant';

@Component({
  selector: 'app-expert-queue',
  standalone: true,
  imports: [CommonModule, RouterLink, VerdictBadgeComponent],
  template: `
    <div class="queue-page">
      <div class="container" style="padding-top:48px; padding-bottom:80px;">
        <div class="page-header animate-in">
          <div class="header-content">
            <div>
              <h1>Expert Review Queue</h1>
              <p>Claims awaiting your expert assessment</p>
            </div>
            <div class="header-actions">
              <span class="badge badge-primary">{{ queue().length }} pending</span>
            </div>
          </div>
        </div>

        @if (loading()) { <div class="loading-overlay"><div class="spinner"></div></div> }

        @if (!loading() && queue().length === 0) {
          <div class="empty-state card text-center">
            <div style="font-size:64px;margin-bottom:16px;">🎉</div>
            <h3>Queue is empty</h3>
            <p>All claims have been reviewed. Check back later.</p>
          </div>
        }

        @if (!loading() && queue().length > 0) {
          <div class="queue-list animate-in">
            @for (item of queue(); track item.claim_id) {
              <div class="queue-card card hoverable">
                <div class="queue-header">
                  <div class="queue-meta">
                    <span class="text-muted text-xs">Submitted {{ item.submitted_at | date:'MMM d, y' }}</span>
                    <div class="vote-count">
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/></svg>
                      {{ item.vote_count }} / 3 votes
                    </div>
                  </div>
                  @if (item.ai_label) {
                    <app-verdict-badge [label]="item.ai_label" />
                  }
                </div>
                <p class="queue-headline">{{ item.headline }}</p>
                <div class="queue-footer">
                  <span class="queue-source text-muted text-sm">{{ item.claimed_source }}</span>
                  @if (item.ai_confidence !== null) {
                    <span class="ai-conf text-sm">
                      AI: <strong>{{ (item.ai_confidence! * 100).toFixed(1) }}%</strong>
                    </span>
                  }
                  <a [routerLink]="['/expert/queue', item.claim_id]" class="btn btn-primary btn-sm">
                    Review →
                  </a>
                </div>
              </div>
            }
          </div>

          <div class="pagination">
            <button class="btn btn-ghost btn-sm" [disabled]="offset() === 0" (click)="prev()">← Prev</button>
            <span class="text-muted text-sm">Page {{ page() }}</span>
            <button class="btn btn-ghost btn-sm" [disabled]="queue().length < limit" (click)="next()">Next →</button>
          </div>
        }
      </div>
    </div>
  `,
  styles: [`
    .queue-page { background: var(--bg-base); min-height: 100%; }
    .page-header { margin-bottom: 32px; }
    .header-content { display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 16px; }
    .header-actions { display: flex; align-items: center; gap: 12px; }
    .page-header h1 { margin-bottom: 8px; }
    .page-header p { color: var(--text-secondary); }
    .queue-list { display: flex; flex-direction: column; gap: 16px; margin-bottom: 24px; }
    .queue-card { padding: 24px; }
    .queue-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; flex-wrap: wrap; gap: 8px; }
    .queue-meta { display: flex; align-items: center; gap: 12px; }
    .vote-count { display: flex; align-items: center; gap: 4px; font-size: 12px; color: var(--text-muted); background: var(--bg-surface-2); padding: 3px 8px; border-radius: var(--radius-full); }
    .queue-headline { font-size: 16px; font-weight: 500; color: var(--text-primary); line-height: 1.5; margin-bottom: 16px; }
    .queue-footer { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
    .queue-source { flex: 1; }
    .ai-conf { color: var(--text-secondary); }
    .empty-state { max-width: 400px; margin: 80px auto; }
    .pagination { display: flex; align-items: center; justify-content: center; gap: 16px; }
    .loading-overlay { display: flex; justify-content: center; padding: 80px; }
  `]
})
export class ExpertQueueComponent implements OnInit {
  private readonly api = inject(ApiService);

  readonly loading = signal(true);
  readonly queue = signal<ExpertQueueItem[]>([]);
  readonly offset = signal(0);
  readonly limit = 20;
  readonly page = () => Math.floor(this.offset() / this.limit) + 1;

  ngOnInit(): void { this.load(); }

  load(): void {
    this.loading.set(true);
    this.api.get<ExpertQueueItem[]>(API_ENDPOINTS.EXPERT_QUEUE, { limit: this.limit, offset: this.offset() })
      .subscribe({ next: q => { this.queue.set(q); this.loading.set(false); }, error: () => this.loading.set(false) });
  }

  prev(): void { this.offset.update(o => Math.max(0, o - this.limit)); this.load(); }
  next(): void { this.offset.update(o => o + this.limit); this.load(); }
}
