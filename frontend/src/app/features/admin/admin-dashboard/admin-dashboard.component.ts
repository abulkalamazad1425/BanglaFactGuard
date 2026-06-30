import { Component, OnInit, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { ApiService } from '../../../core/services/api.service';
import { AdminStats, ExpertResponse } from '../../../core/models/admin.model';
import { ScoreBarComponent } from '../../../shared/components/score-bar/score-bar.component';
import { API_ENDPOINTS } from '../../../core/constants/api-endpoints.constant';

@Component({
  selector: 'app-admin-dashboard',
  standalone: true,
  imports: [CommonModule, RouterLink, ScoreBarComponent],
  template: `
    <div class="admin-page">
      <div class="container" style="padding-top:48px; padding-bottom:80px;">
        <div class="page-header animate-in">
          <div class="header-content">
            <div>
              <h1>Admin Dashboard</h1>
              <p>Platform overview and management</p>
            </div>
            <div class="header-links">
              <a routerLink="/admin/experts" class="btn btn-secondary">Manage Experts</a>
              <a routerLink="/admin/stats" class="btn btn-primary">Full Stats</a>
            </div>
          </div>
        </div>

        @if (loading()) { <div class="loading-overlay"><div class="spinner"></div></div> }

        @if (!loading() && stats()) {
          <div class="animate-in">
            <!-- Metric Cards -->
            <div class="grid-4" style="margin-bottom:32px;">
              <div class="metric-card card">
                <div class="metric-icon">📊</div>
                <span class="metric-num">{{ stats()!.total_submissions }}</span>
                <span class="metric-lbl">Total Submissions</span>
              </div>
              <div class="metric-card card">
                <div class="metric-icon">📅</div>
                <span class="metric-num">{{ stats()!.submissions_last_30_days }}</span>
                <span class="metric-lbl">Last 30 Days</span>
              </div>
              <div class="metric-card card">
                <div class="metric-icon">👤</div>
                <span class="metric-num">{{ stats()!.active_experts }} / {{ stats()!.total_experts }}</span>
                <span class="metric-lbl">Active Experts</span>
              </div>
              <div class="metric-card card text-warning">
                <div class="metric-icon">⏳</div>
                <span class="metric-num">{{ stats()!.pending_expert_reviews }}</span>
                <span class="metric-lbl">Pending Reviews</span>
              </div>
            </div>

            <!-- Verdict Breakdown -->
            <div class="grid-2" style="margin-bottom:32px;">
              <div class="card">
                <h3 class="card-title">Verdict Breakdown</h3>
                <div class="breakdown-list">
                  <app-score-bar label="True ✓" [value]="trueRatio()" color="var(--success)" />
                  <app-score-bar label="False ✗" [value]="falseRatio()" color="var(--error)" />
                  <app-score-bar label="Partially True ◑" [value]="partialRatio()" color="var(--warning)" />
                  <app-score-bar label="Not Found ?" [value]="nfRatio()" color="var(--text-muted)" />
                </div>
                <div class="breakdown-counts">
                  <span class="text-success">{{ stats()!.verdict_breakdown.true_count }} TRUE</span>
                  <span class="text-error">{{ stats()!.verdict_breakdown.false_count }} FALSE</span>
                  <span class="text-warning">{{ stats()!.verdict_breakdown.partially_true_count }} PARTIAL</span>
                  <span class="text-muted">{{ stats()!.verdict_breakdown.not_found_count }} NF</span>
                </div>
              </div>

              <div class="card">
                <h3 class="card-title">Quick Actions</h3>
                <div class="quick-actions">
                  <a routerLink="/admin/experts/new" class="action-link">
                    <span class="action-icon">➕</span>
                    <div>
                      <div class="action-title">Create Expert Account</div>
                      <div class="action-desc text-muted text-sm">Add a new expert reviewer</div>
                    </div>
                  </a>
                  <a routerLink="/admin/experts" class="action-link">
                    <span class="action-icon">👥</span>
                    <div>
                      <div class="action-title">Manage Experts</div>
                      <div class="action-desc text-muted text-sm">View, edit, or deactivate experts</div>
                    </div>
                  </a>
                  <a routerLink="/dashboard" class="action-link">
                    <span class="action-icon">📈</span>
                    <div>
                      <div class="action-title">Public Dashboard</div>
                      <div class="action-desc text-muted text-sm">View public-facing statistics</div>
                    </div>
                  </a>
                </div>
              </div>
            </div>
          </div>
        }
      </div>
    </div>
  `,
  styles: [`
    .admin-page { background: var(--bg-base); min-height: 100%; }
    .page-header { margin-bottom: 32px; }
    .header-content { display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 16px; h1 { margin-bottom: 8px; } p { color: var(--text-secondary); } }
    .header-links { display: flex; gap: 12px; }
    .metric-card { padding: 24px; }
    .metric-icon { font-size: 28px; margin-bottom: 12px; }
    .metric-num { display: block; font-size: 2rem; font-weight: 800; font-family: var(--font-display); margin-bottom: 4px; }
    .metric-lbl { font-size: 12px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; }
    .card-title { font-size: 15px; margin-bottom: 20px; }
    .breakdown-list { display: flex; flex-direction: column; gap: 16px; margin-bottom: 20px; }
    .breakdown-counts { display: flex; gap: 16px; flex-wrap: wrap; font-size: 13px; font-weight: 600; padding-top: 16px; border-top: 1px solid var(--border); }
    .quick-actions { display: flex; flex-direction: column; gap: 8px; }
    .action-link { display: flex; align-items: center; gap: 16px; padding: 16px; border-radius: var(--radius-md); background: var(--bg-surface-2); text-decoration: none; color: var(--text-primary); border: 1px solid var(--border); transition: var(--transition); &:hover { border-color: var(--primary); background: rgba(124,106,247,0.05); } }
    .action-icon { font-size: 24px; flex-shrink: 0; }
    .action-title { font-weight: 600; font-size: 14px; margin-bottom: 2px; }
    .loading-overlay { display: flex; justify-content: center; padding: 80px; }
  `]
})
export class AdminDashboardComponent implements OnInit {
  private readonly api = inject(ApiService);

  readonly loading = signal(true);
  readonly stats = signal<AdminStats | null>(null);

  get total() { const bd = this.stats()?.verdict_breakdown; return bd ? bd.true_count + bd.false_count + bd.partially_true_count + bd.not_found_count : 1; }
  trueRatio    = () => (this.stats()?.verdict_breakdown.true_count ?? 0) / this.total;
  falseRatio   = () => (this.stats()?.verdict_breakdown.false_count ?? 0) / this.total;
  partialRatio = () => (this.stats()?.verdict_breakdown.partially_true_count ?? 0) / this.total;
  nfRatio      = () => (this.stats()?.verdict_breakdown.not_found_count ?? 0) / this.total;

  ngOnInit(): void {
    this.api.get<AdminStats>(API_ENDPOINTS.ADMIN_STATS).subscribe({
      next: s => { this.stats.set(s); this.loading.set(false); },
      error: () => this.loading.set(false),
    });
  }
}
