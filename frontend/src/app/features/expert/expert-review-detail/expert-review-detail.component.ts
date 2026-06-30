import { Component, OnInit, inject, signal } from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { CommonModule } from '@angular/common';
import { ApiService } from '../../../core/services/api.service';
import { ToastService } from '../../../shared/services/toast.service';
import { ExpertQueueItem, ExpertReviewResponse } from '../../../core/models/expert.model';
import { VerdictBadgeComponent } from '../../../shared/components/verdict-badge/verdict-badge.component';
import { ScoreBarComponent } from '../../../shared/components/score-bar/score-bar.component';
import { API_ENDPOINTS } from '../../../core/constants/api-endpoints.constant';

const LABELS = ['TRUE', 'FALSE', 'PARTIALLY_TRUE', 'NOT_FOUND_IN_CLAIMED_SOURCE'] as const;
type Label = typeof LABELS[number];

@Component({
  selector: 'app-expert-review-detail',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, RouterLink, VerdictBadgeComponent, ScoreBarComponent],
  template: `
    <div class="review-page">
      <div class="container container-sm" style="padding-top:48px; padding-bottom:80px;">
        <div class="topbar animate-in">
          <a routerLink="/expert/queue" class="btn btn-ghost btn-sm">← Back to Queue</a>
        </div>

        @if (loading()) { <div class="loading-overlay"><div class="spinner"></div></div> }

        @if (!loading() && claim()) {
          <div class="animate-in">
            <!-- Claim info -->
            <div class="card claim-card">
              <div class="claim-header">
                <h2>Claim Details</h2>
                <app-verdict-badge [label]="claim()!.ai_label" />
              </div>
              <p class="claim-headline">{{ claim()!.headline }}</p>
              <div class="claim-meta">
                <span class="text-muted text-sm">Source: <a [href]="claim()!.claimed_source" target="_blank">{{ claim()!.claimed_source }}</a></span>
                <span class="text-muted text-sm">Submitted: {{ claim()!.submitted_at | date:'MMM d, y, HH:mm' }}</span>
              </div>
              @if (claim()!.ai_confidence !== null) {
                <div style="max-width:300px; margin-top:16px;">
                  <app-score-bar label="AI Confidence" [value]="claim()!.ai_confidence!" />
                </div>
              }
              <div class="vote-status">
                <span class="text-muted text-sm">{{ claim()!.vote_count }} / 3 expert votes submitted</span>
                <div class="vote-progress">
                  <div class="vote-fill" [style.width.%]="(claim()!.vote_count / 3) * 100"></div>
                </div>
              </div>
            </div>

            <!-- Vote Form -->
            @if (!submitted()) {
              <div class="card vote-card">
                <h3>Submit Your Assessment</h3>
                <form [formGroup]="form" (ngSubmit)="onSubmit()">
                  <div class="form-group">
                    <label class="form-label">Your Verdict <span style="color:var(--error)">*</span></label>
                    <div class="verdict-options">
                      @for (lbl of labels; track lbl) {
                        <button type="button" class="verdict-option"
                                [class.selected]="selectedLabel() === lbl"
                                [ngClass]="lbl === 'TRUE' ? 'option-true' : lbl === 'FALSE' ? 'option-false' : lbl === 'PARTIALLY_TRUE' ? 'option-partial' : 'option-notfound'"
                                (click)="selectLabel(lbl)">
                          {{ labelDisplay[lbl] }}
                        </button>
                      }
                    </div>
                    @if (!selectedLabel() && formSubmitted) {
                      <span class="form-error">Please select a verdict</span>
                    }
                  </div>

                  <div class="form-group">
                    <label class="form-label">Justification <span style="color:var(--error)">*</span> <span class="text-muted text-xs">(min 50 characters)</span></label>
                    <textarea formControlName="justification" class="form-control"
                              [class.is-invalid]="justInvalid"
                              rows="5"
                              placeholder="Explain your reasoning (minimum 50 characters). What evidence supports your verdict?">
                    </textarea>
                    <div class="char-count" [class.valid]="charCount >= 50">{{ charCount }} / 50+</div>
                    @if (justInvalid) {
                      <span class="form-error">Justification must be at least 50 characters</span>
                    }
                  </div>

                  <button type="submit" class="btn btn-primary btn-full btn-lg" [disabled]="voting()">
                    @if (voting()) { <span class="btn-spinner"></span> Submitting... }
                    @else { ⚖️ Submit Vote }
                  </button>
                </form>
              </div>
            } @else {
              <div class="card success-card text-center">
                <div style="font-size:56px; margin-bottom:16px;">✅</div>
                <h3>Vote Submitted!</h3>
                <p>Your assessment has been recorded. The final verdict will be determined once all minimum votes are in.</p>
                <a routerLink="/expert/queue" class="btn btn-primary mt-4">Back to Queue</a>
              </div>
            }
          </div>
        }
      </div>
    </div>
  `,
  styles: [`
    .review-page { background: var(--bg-base); min-height: 100%; }
    .topbar { margin-bottom: 24px; }
    .claim-card { margin-bottom: 24px; }
    .claim-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; flex-wrap: wrap; gap: 12px; h2 { font-size: 1.1rem; } }
    .claim-headline { font-size: 18px; font-weight: 500; line-height: 1.5; margin-bottom: 16px; }
    .claim-meta { display: flex; gap: 24px; flex-wrap: wrap; a { color: var(--primary-light); } }
    .vote-status { margin-top: 20px; }
    .vote-progress { height: 6px; background: var(--bg-surface-3); border-radius: var(--radius-full); margin-top: 8px; overflow: hidden; }
    .vote-fill { height: 100%; background: var(--gradient-primary); border-radius: var(--radius-full); transition: width 0.5s ease; }
    .vote-card h3 { font-size: 1.1rem; margin-bottom: 24px; }
    .form-group { margin-bottom: 24px; }
    .verdict-options { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; margin-top: 8px;
      @media (max-width: 480px) { grid-template-columns: 1fr; }
    }
    .verdict-option {
      padding: 12px 16px; border-radius: var(--radius-md); border: 2px solid var(--border);
      background: var(--bg-surface-2); color: var(--text-secondary); cursor: pointer;
      font-size: 14px; font-weight: 600; transition: var(--transition);
      &:hover { border-color: var(--border-hover); color: var(--text-primary); }
      &.selected { color: white; border-color: transparent; }
      &.option-true.selected    { background: var(--success); }
      &.option-false.selected   { background: var(--error); }
      &.option-partial.selected { background: var(--warning); }
      &.option-notfound.selected{ background: var(--text-muted); }
    }
    .char-count { font-size: 12px; color: var(--text-muted); margin-top: 6px; text-align: right; &.valid { color: var(--success); } }
    .success-card { }
    .loading-overlay { display: flex; justify-content: center; padding: 80px; }
    .btn-spinner { width: 18px; height: 18px; border: 2px solid rgba(255,255,255,0.3); border-top-color: white; border-radius: 50%; animation: spin 0.7s linear infinite; }
  `]
})
export class ExpertReviewDetailComponent implements OnInit {
  private readonly api = inject(ApiService);
  private readonly route = inject(ActivatedRoute);
  private readonly toast = inject(ToastService);
  private readonly fb = inject(FormBuilder);

  readonly loading = signal(true);
  readonly voting = signal(false);
  readonly submitted = signal(false);
  readonly claim = signal<ExpertQueueItem | null>(null);
  readonly selectedLabel = signal<Label | null>(null);
  formSubmitted = false;

  readonly labels = LABELS;
  readonly labelDisplay: Record<Label, string> = {
    'TRUE': '✓ True',
    'FALSE': '✗ False',
    'PARTIALLY_TRUE': '◑ Partially True',
    'NOT_FOUND_IN_CLAIMED_SOURCE': '? Not Found',
  };

  form = this.fb.group({
    justification: ['', [Validators.required, Validators.minLength(50)]],
  });

  get justInvalid() { return this.form.get('justification')?.invalid && this.form.get('justification')?.touched; }
  get charCount() { return (this.form.value.justification || '').length; }

  selectLabel(lbl: Label): void { this.selectedLabel.set(lbl); }

  ngOnInit(): void {
    const claimId = this.route.snapshot.paramMap.get('id');
    if (!claimId) { this.loading.set(false); return; }

    this.api.get<ExpertQueueItem>(`${API_ENDPOINTS.EXPERT_QUEUE}/${claimId}`).subscribe({
      next: c => { this.claim.set(c); this.loading.set(false); },
      error: () => this.loading.set(false),
    });
  }

  onSubmit(): void {
    this.formSubmitted = true;
    if (this.form.invalid || !this.selectedLabel()) {
      this.form.markAllAsTouched();
      return;
    }
    const claimId = this.route.snapshot.paramMap.get('id');
    this.voting.set(true);

    this.api.post(`${API_ENDPOINTS.EXPERT_QUEUE}/${claimId}/vote`, {
      expert_label: this.selectedLabel(),
      justification: this.form.value.justification,
    }).subscribe({
      next: () => { this.submitted.set(true); this.voting.set(false); this.toast.success('Vote submitted successfully!'); },
      error: err => { this.voting.set(false); this.toast.error(err.error?.message || 'Failed to submit vote.'); },
    });
  }
}
