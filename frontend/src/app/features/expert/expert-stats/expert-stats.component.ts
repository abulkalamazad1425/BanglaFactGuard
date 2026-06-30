import { Component, OnInit, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ApiService } from '../../../core/services/api.service';
import { ExpertStats } from '../../../core/models/expert.model';
import { ScoreBarComponent } from '../../../shared/components/score-bar/score-bar.component';
import { API_ENDPOINTS } from '../../../core/constants/api-endpoints.constant';

@Component({
  selector: 'app-expert-stats',
  standalone: true,
  imports: [CommonModule, ScoreBarComponent],
  template: `
    <div class="stats-page">
      <div class="container container-sm" style="padding-top:48px; padding-bottom:80px;">
        <div class="page-header animate-in">
          <h1>My Expert Stats</h1>
          <p>Your credibility score and performance metrics</p>
        </div>

        @if (loading()) { <div class="loading-overlay"><div class="spinner"></div></div> }

        @if (!loading() && stats()) {
          <div class="animate-in">
            <!-- Credibility Card -->
            <div class="credibility-card card">
              <div class="cred-header">
                <div>
                  <h2 class="cred-title">Credibility Score</h2>
                  <p class="text-muted text-sm">System-computed based on voting accuracy</p>
                </div>
                <div class="cred-score" [style.color]="scoreColor()">
                  {{ (stats()!.current_credibility * 100).toFixed(1) }}%
                </div>
              </div>
              <div style="margin-top:20px;">
                <app-score-bar label="Credibility" [value]="stats()!.current_credibility" [color]="scoreColor()" />
              </div>
              <div class="cred-legend">
                <span>🔴 Low (0–40%)</span>
                <span>🟡 Medium (40–70%)</span>
                <span>🟢 High (70–100%)</span>
              </div>
            </div>

            <!-- Stats Grid -->
            <div class="grid-3" style="margin-top:24px;">
              <div class="stat-card card text-center">
                <span class="stat-num">{{ stats()!.total_votes }}</span>
                <span class="stat-lbl">Total Votes</span>
              </div>
              <div class="stat-card card text-center text-success">
                <span class="stat-num">{{ stats()!.correct_votes }}</span>
                <span class="stat-lbl">Correct Votes</span>
              </div>
              <div class="stat-card card text-center">
                <span class="stat-num">{{ stats()!.accuracy_pct !== null ? stats()!.accuracy_pct + '%' : 'N/A' }}</span>
                <span class="stat-lbl">Accuracy</span>
              </div>
            </div>

            <!-- Info -->
            <div class="info-card card" style="margin-top:24px;">
              <h3 style="font-size:15px; margin-bottom:12px;">How Credibility Works</h3>
              <ul class="info-list">
                <li>✅ Correct vote: +0.05 score (capped at 1.0)</li>
                <li>❌ Wrong vote: −0.03 score (floor at 0.1)</li>
                <li>⚖️ Your credibility weights your votes in the final verdict calculation</li>
                <li>🔒 Scores are computed automatically — no manual override</li>
              </ul>
            </div>
          </div>
        }
      </div>
    </div>
  `,
  styles: [`
    .stats-page { background: var(--bg-base); min-height: 100%; }
    .page-header { margin-bottom: 32px; h1 { margin-bottom: 8px; } p { color: var(--text-secondary); } }
    .credibility-card { padding: 32px; }
    .cred-header { display: flex; justify-content: space-between; align-items: flex-start; }
    .cred-title { font-size: 1.25rem; margin-bottom: 4px; }
    .cred-score { font-size: 3rem; font-weight: 800; font-family: var(--font-display); }
    .cred-legend { display: flex; gap: 20px; margin-top: 16px; font-size: 12px; color: var(--text-muted); flex-wrap: wrap; }
    .stat-card { padding: 24px; }
    .stat-num { display: block; font-size: 2.5rem; font-weight: 800; font-family: var(--font-display); }
    .stat-lbl { font-size: 12px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; margin-top: 4px; display: block; }
    .info-list { list-style: none; display: flex; flex-direction: column; gap: 10px; font-size: 14px; color: var(--text-secondary); }
    .loading-overlay { display: flex; justify-content: center; padding: 80px; }
  `]
})
export class ExpertStatsComponent implements OnInit {
  private readonly api = inject(ApiService);

  readonly loading = signal(true);
  readonly stats = signal<ExpertStats | null>(null);

  scoreColor = () => {
    const s = this.stats()?.current_credibility ?? 0;
    if (s >= 0.7) return 'var(--success)';
    if (s >= 0.4) return 'var(--warning)';
    return 'var(--error)';
  };

  ngOnInit(): void {
    this.api.get<ExpertStats>(API_ENDPOINTS.EXPERT_STATS).subscribe({
      next: s => { this.stats.set(s); this.loading.set(false); },
      error: () => this.loading.set(false),
    });
  }
}
