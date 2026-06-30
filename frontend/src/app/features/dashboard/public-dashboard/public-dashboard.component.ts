import { Component, OnInit, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ApiService } from '../../../core/services/api.service';
import { PublicStats, TopSource } from '../../../core/models/admin.model';
import { ScoreBarComponent } from '../../../shared/components/score-bar/score-bar.component';
import { API_ENDPOINTS } from '../../../core/constants/api-endpoints.constant';

@Component({
  selector: 'app-public-dashboard',
  standalone: true,
  imports: [CommonModule, ScoreBarComponent],
  template: `
    <div class="dashboard-page">
      <div class="container" style="padding-top:48px; padding-bottom:80px;">
        <div class="page-header animate-in">
          <h1>Platform Dashboard</h1>
          <p>Live statistics from the BanglaFactGuard platform</p>
        </div>

        @if (loading()) { <div class="loading-overlay"><div class="spinner"></div></div> }

        @if (!loading() && stats()) {
          <div class="animate-in">
            <!-- Stats Overview -->
            <div class="grid-4" style="margin-bottom:32px;">
              <div class="stat-card card text-center">
                <span class="stat-num">{{ stats()!.total_submissions | number }}</span>
                <span class="stat-lbl">Total Claims</span>
              </div>
              <div class="stat-card card text-center text-success">
                <span class="stat-num">{{ stats()!.true_count | number }}</span>
                <span class="stat-lbl">Verified True</span>
              </div>
              <div class="stat-card card text-center text-error">
                <span class="stat-num">{{ stats()!.false_count | number }}</span>
                <span class="stat-lbl">Found False</span>
              </div>
              <div class="stat-card card text-center">
                <span class="stat-num">{{ stats()!.pending_count | number }}</span>
                <span class="stat-lbl">Pending</span>
              </div>
            </div>

            <!-- Verdict Bars -->
            <div class="grid-2">
              <div class="card">
                <h3 class="card-title">Verdict Distribution</h3>
                <div class="bar-list">
                  <app-score-bar label="True ✓" [value]="ratio(stats()!.true_count)" color="var(--success)" />
                  <app-score-bar label="False ✗" [value]="ratio(stats()!.false_count)" color="var(--error)" />
                  <app-score-bar label="Partially True ◑" [value]="ratio(stats()!.partially_true_count)" color="var(--warning)" />
                  <app-score-bar label="Not Found ?" [value]="ratio(stats()!.not_found_count)" color="var(--text-secondary)" />
                </div>
                <p class="text-muted text-xs mt-4">Excluding {{ stats()!.pending_count }} pending submissions</p>
              </div>

              <div class="card">
                <h3 class="card-title">Top Sources Claimed</h3>
                @if (topSources().length) {
                  <div class="sources-list">
                    @for (src of topSources(); track src.source; let i = $index) {
                      <div class="source-item">
                        <span class="source-rank">{{ i + 1 }}</span>
                        <span class="source-name truncate">{{ src.source }}</span>
                        <span class="source-count badge badge-primary">{{ src.count }}</span>
                      </div>
                    }
                  </div>
                } @else {
                  <p class="text-muted text-sm">No source data available yet.</p>
                }
              </div>
            </div>
          </div>
        }
      </div>
    </div>
  `,
  styles: [`
    .dashboard-page { background: var(--bg-base); min-height: 100%; }
    .page-header { margin-bottom: 32px; h1 { margin-bottom: 8px; } p { color: var(--text-secondary); } }
    .stat-card { padding: 24px; }
    .stat-num { display: block; font-size: 2.5rem; font-weight: 800; font-family: var(--font-display); }
    .stat-lbl { font-size: 12px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; }
    .card-title { font-size: 15px; margin-bottom: 20px; }
    .bar-list { display: flex; flex-direction: column; gap: 16px; }
    .sources-list { display: flex; flex-direction: column; gap: 10px; }
    .source-item { display: flex; align-items: center; gap: 12px; }
    .source-rank { width: 24px; height: 24px; border-radius: 50%; background: var(--bg-surface-3); display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 700; color: var(--text-muted); flex-shrink: 0; }
    .source-name { flex: 1; font-size: 14px; }
    .source-count { flex-shrink: 0; }
    .loading-overlay { display: flex; justify-content: center; padding: 80px; }
  `]
})
export class PublicDashboardComponent implements OnInit {
  private readonly api = inject(ApiService);

  readonly loading = signal(true);
  readonly stats = signal<PublicStats | null>(null);
  readonly topSources = signal<TopSource[]>([]);

  ratio = (count: number) => {
    const total = this.stats()!.total_submissions - this.stats()!.pending_count;
    return total > 0 ? count / total : 0;
  };

  ngOnInit(): void {
    this.api.get<PublicStats>(API_ENDPOINTS.DASHBOARD_STATS).subscribe({
      next: s => { this.stats.set(s); this.loading.set(false); },
      error: () => this.loading.set(false),
    });
    this.api.get<TopSource[]>(API_ENDPOINTS.DASHBOARD_TOP_SOURCES, { limit: 10 }).subscribe({
      next: t => this.topSources.set(t), error: () => {},
    });
  }
}
