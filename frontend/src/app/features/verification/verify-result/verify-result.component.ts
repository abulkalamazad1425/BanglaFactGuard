import { Component, OnInit, inject, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { CommonModule } from '@angular/common';
import { ApiService } from '../../../core/services/api.service';
import { VerificationResult } from '../../../core/models/verification.model';
import { VerdictBadgeComponent } from '../../../shared/components/verdict-badge/verdict-badge.component';
import { ScoreBarComponent } from '../../../shared/components/score-bar/score-bar.component';
import { API_ENDPOINTS } from '../../../core/constants/api-endpoints.constant';

const VERDICT_COLORS: Record<string, string> = {
  'TRUE': 'var(--success)',
  'FALSE': 'var(--error)',
  'PARTIALLY_TRUE': 'var(--warning)',
  'NOT_FOUND_IN_CLAIMED_SOURCE': 'var(--text-secondary)',
};

@Component({
  selector: 'app-verify-result',
  standalone: true,
  imports: [CommonModule, RouterLink, VerdictBadgeComponent, ScoreBarComponent],
  template: `
    <div class="result-page">
      <div class="container" style="padding-top:48px; padding-bottom:80px;">

        @if (loading()) {
          <div class="loading-overlay">
            <div class="loading-card card text-center">
              <div class="spinner" style="margin: 0 auto 20px;"></div>
              <h3>Loading result...</h3>
              <p>Fetching verification details</p>
            </div>
          </div>
        }

        @if (!loading() && result()) {
          <div class="animate-in">
            <!-- Top bar -->
            <div class="result-topbar">
              <a routerLink="/verify" class="btn btn-ghost btn-sm">← New Verification</a>
              <span class="claim-id">ID: {{ result()!.claim_id }}</span>
            </div>

            <!-- Verdict Card -->
            <div class="verdict-hero card" [style.border-color]="verdictColor()">
              <div class="verdict-content">
                <div class="verdict-label">
                  <app-verdict-badge [label]="result()!.label" />
                  <span class="verdict-title">{{ verdictTitle() }}</span>
                </div>
                @if (result()!.explanation) {
                  <p class="verdict-explanation">{{ result()!.explanation }}</p>
                }
                <div class="verdict-scores">
                  <app-score-bar label="AI Confidence" [value]="result()!.confidence" [color]="verdictColor()" />
                </div>
              </div>
              <div class="verdict-meta">
                <div class="meta-item">
                  <span class="meta-label">Status</span>
                  <span class="badge badge-primary">{{ result()!.status }}</span>
                </div>
                @if (result()!.processing_time_ms) {
                  <div class="meta-item">
                    <span class="meta-label">Processing Time</span>
                    <span>{{ (result()!.processing_time_ms! / 1000).toFixed(1) }}s</span>
                  </div>
                }
              </div>
            </div>

            <div class="result-grid">
              <!-- Evidence Articles -->
              @if (result()!.evidence_articles?.length) {
                <div class="card evidence-card">
                  <h3 class="section-title">📰 Evidence Articles ({{ result()!.evidence_articles!.length }})</h3>
                  <div class="evidence-list">
                    @for (art of result()!.evidence_articles!; track art.url) {
                      <div class="evidence-item">
                        <div class="evidence-header">
                          <a [href]="art.url" target="_blank" class="evidence-title">{{ art.title || art.url }}</a>
                          <span class="evidence-source badge badge-primary">{{ art.source }}</span>
                        </div>
                        @if (art.semantic_similarity !== undefined) {
                          <div class="evidence-scores">
                            <app-score-bar label="Semantic Sim." [value]="art.semantic_similarity!" color="var(--primary)" />
                            @if (art.nli_score !== undefined) {
                              <app-score-bar label="NLI Score" [value]="art.nli_score!" color="var(--accent)" />
                            }
                          </div>
                        }
                      </div>
                    }
                  </div>
                </div>
              }

              <!-- Verification Checks -->
              @if (result()!.checks?.length) {
                <div class="card checks-card">
                  <h3 class="section-title">✅ Verification Checks</h3>
                  <div class="checks-list">
                    @for (chk of result()!.checks!; track chk.stage) {
                      <div class="check-item" [class.passed]="chk.passed" [class.failed]="!chk.passed">
                        <span class="check-icon">{{ chk.passed ? '✓' : '✗' }}</span>
                        <div class="check-body">
                          <span class="check-stage">{{ chk.stage }}</span>
                          @if (chk.detail) {
                            <span class="check-detail">{{ chk.detail }}</span>
                          }
                        </div>
                      </div>
                    }
                  </div>
                </div>
              }
            </div>

            <!-- Share -->
            <div class="share-bar card">
              <span>🔗 Share this result:</span>
              <input type="text" [value]="shareUrl()" readonly class="form-control share-input" (click)="copyUrl()" />
              <button class="btn btn-secondary btn-sm" (click)="copyUrl()">{{ copied ? '✓ Copied' : 'Copy' }}</button>
            </div>
          </div>
        }

        @if (!loading() && !result()) {
          <div class="not-found card text-center">
            <div style="font-size:64px; margin-bottom:20px;">🔎</div>
            <h2>Result not found</h2>
            <p>This claim ID doesn't exist or has been removed.</p>
            <a routerLink="/verify" class="btn btn-primary mt-4">Submit New Claim</a>
          </div>
        }
      </div>
    </div>
  `,
  styles: [`
    .result-page { background: var(--bg-base); min-height: 100%; }
    .result-topbar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; }
    .claim-id { font-size: 12px; color: var(--text-muted); font-family: monospace; }
    .verdict-hero { padding: 32px; border-width: 2px !important; margin-bottom: 24px; }
    .verdict-content { margin-bottom: 24px; }
    .verdict-label { display: flex; align-items: center; gap: 16px; margin-bottom: 16px; flex-wrap: wrap; }
    .verdict-title { font-size: 1.5rem; font-weight: 700; font-family: var(--font-display); }
    .verdict-explanation { color: var(--text-secondary); margin-bottom: 24px; font-size: 15px; line-height: 1.7; }
    .verdict-scores { max-width: 400px; }
    .verdict-meta { display: flex; gap: 24px; padding-top: 24px; border-top: 1px solid var(--border); }
    .meta-item { display: flex; flex-direction: column; gap: 6px; }
    .meta-label { font-size: 11px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; }
    .result-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; margin-bottom: 24px;
      @media (max-width: 768px) { grid-template-columns: 1fr; }
    }
    .section-title { font-size: 16px; margin-bottom: 20px; }
    .evidence-item { padding: 16px 0; border-bottom: 1px solid var(--border); &:last-child { border-bottom: none; } }
    .evidence-header { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; margin-bottom: 12px; flex-wrap: wrap; }
    .evidence-title { font-size: 14px; color: var(--primary-light); font-weight: 500; flex: 1; line-height: 1.4; }
    .evidence-scores { display: flex; flex-direction: column; gap: 8px; }
    .check-item { display: flex; align-items: flex-start; gap: 12px; padding: 10px 12px; border-radius: var(--radius-md); margin-bottom: 8px;
      &.passed { background: var(--success-bg); }
      &.failed  { background: var(--error-bg); }
    }
    .check-icon { font-weight: 700; font-size: 14px; padding-top: 2px; }
    .check-item.passed .check-icon { color: var(--success); }
    .check-item.failed  .check-icon { color: var(--error); }
    .check-body { display: flex; flex-direction: column; gap: 2px; }
    .check-stage { font-size: 13px; font-weight: 500; }
    .check-detail { font-size: 12px; color: var(--text-secondary); }
    .share-bar { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
    .share-input { cursor: pointer; max-width: 400px; font-size: 13px; }
    .loading-card { max-width: 300px; margin: 80px auto; }
    .not-found { max-width: 400px; margin: 80px auto; }
  `]
})
export class VerifyResultComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly api = inject(ApiService);

  readonly loading = signal(true);
  readonly result = signal<VerificationResult | null>(null);
  copied = false;

  readonly verdictColor = () => {
    const label = this.result()?.label;
    return label ? VERDICT_COLORS[label] ?? 'var(--text-secondary)' : 'var(--border)';
  };

  readonly verdictTitle = () => {
    const m: Record<string, string> = {
      'TRUE': 'This claim appears to be TRUE',
      'FALSE': 'This claim appears to be FALSE',
      'PARTIALLY_TRUE': 'This claim is PARTIALLY TRUE',
      'NOT_FOUND_IN_CLAIMED_SOURCE': 'Source NOT FOUND for this claim',
    };
    return this.result()?.label ? m[this.result()!.label] || '' : '';
  };

  shareUrl = () => `${window.location.origin}/verify/${this.result()?.claim_id}`;

  ngOnInit(): void {
    const id = this.route.snapshot.paramMap.get('id');
    if (!id) { this.loading.set(false); return; }

    this.api.get<VerificationResult>(`${API_ENDPOINTS.VERIFICATION}/${id}`).subscribe({
      next: r => { this.result.set(r); this.loading.set(false); },
      error: () => { this.loading.set(false); },
    });
  }

  copyUrl(): void {
    navigator.clipboard.writeText(this.shareUrl());
    this.copied = true;
    setTimeout(() => this.copied = false, 2000);
  }
}
