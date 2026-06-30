import { Component, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { CommonModule } from '@angular/common';
import { ApiService } from '../../../core/services/api.service';
import { ToastService } from '../../../shared/services/toast.service';
import { VerificationResult } from '../../../core/models/verification.model';
import { API_ENDPOINTS } from '../../../core/constants/api-endpoints.constant';

@Component({
  selector: 'app-verify-claim',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, RouterLink],
  template: `
    <div class="verify-page">
      <div class="container container-sm" style="padding-top:48px; padding-bottom:80px;">

        <!-- Header -->
        <div class="page-header text-center animate-in">
          <div class="page-icon">🔍</div>
          <h1>Verify a News Claim</h1>
          <p>Submit a headline and its claimed source. Our 12-stage AI pipeline will verify it.</p>
        </div>

        <!-- Form -->
        <div class="card verify-card animate-in" style="animation-delay:0.1s">
          <form [formGroup]="form" (ngSubmit)="onSubmit()">
            <div class="form-group">
              <label class="form-label">News Headline <span class="required">*</span></label>
              <textarea formControlName="headline" class="form-control"
                        [class.is-invalid]="headlineInvalid"
                        rows="3"
                        placeholder="Enter the Bangla news headline to verify..."></textarea>
              @if (headlineInvalid) {
                <span class="form-error">Headline is required (min 10 characters)</span>
              }
            </div>

            <div class="form-group">
              <label class="form-label">Article Body <span class="optional">(optional)</span></label>
              <textarea formControlName="body" class="form-control" rows="4"
                        placeholder="Paste the article body for more accurate verification..."></textarea>
            </div>

            <div class="form-group">
              <label class="form-label">Claimed Source URL <span class="required">*</span></label>
              <input type="url" formControlName="claimed_source" class="form-control"
                     [class.is-invalid]="sourceInvalid"
                     placeholder="https://www.prothomalo.com/..." />
              @if (sourceInvalid) {
                <span class="form-error">Valid URL is required</span>
              }
            </div>

            <div class="form-tips">
              <div class="tip">
                <span>💡</span>
                <span>Provide the full URL of the news source (e.g., prothomalo.com, bdnews24.com)</span>
              </div>
              <div class="tip">
                <span>⚡</span>
                <span>Verification typically takes 15–60 seconds depending on server load</span>
              </div>
            </div>

            <button type="submit" class="btn btn-primary btn-full btn-lg" [disabled]="loading">
              @if (loading) {
                <span class="btn-spinner"></span>
                Verifying... (this may take up to 60s)
              } @else {
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>
                Verify Claim
              }
            </button>
          </form>
        </div>

        <!-- Recent results hint -->
        <div class="result-hint animate-in" style="animation-delay:0.2s">
          <p class="text-center text-muted text-sm">
            Anonymous submissions are supported. <a routerLink="/auth/register">Create an account</a> to track your history.
          </p>
        </div>

      </div>
    </div>
  `,
  styles: [`
    .verify-page { background: var(--bg-base); min-height: 100%; }
    .page-header { margin-bottom: 48px; }
    .page-icon { font-size: 64px; margin-bottom: 20px; }
    .page-header h1 { margin-bottom: 12px; }
    .page-header p { color: var(--text-secondary); font-size: 16px; max-width: 500px; margin: 0 auto; }
    .verify-card { padding: 40px; }
    .required { color: var(--error); }
    .optional { color: var(--text-muted); font-size: 12px; }
    .form-group { margin-bottom: 24px; }
    .form-tips { margin: 24px 0; display: flex; flex-direction: column; gap: 8px; }
    .tip {
      display: flex; align-items: flex-start; gap: 10px;
      font-size: 13px; color: var(--text-muted); padding: 10px 14px;
      background: var(--bg-surface-2); border-radius: var(--radius-md);
    }
    .result-hint { margin-top: 24px; a { color: var(--primary-light); } }
    .btn-spinner { width: 18px; height: 18px; border: 2px solid rgba(255,255,255,0.3); border-top-color: white; border-radius: 50%; animation: spin 0.7s linear infinite; }
  `]
})
export class VerifyClaimComponent {
  private readonly fb = inject(FormBuilder);
  private readonly api = inject(ApiService);
  private readonly router = inject(Router);
  private readonly toast = inject(ToastService);

  loading = false;

  form = this.fb.group({
    headline: ['', [Validators.required, Validators.minLength(10)]],
    body: [''],
    claimed_source: ['', [Validators.required, Validators.pattern(/^https?:\/\/.+/)]],
  });

  get headlineInvalid() { return this.form.get('headline')?.invalid && this.form.get('headline')?.touched; }
  get sourceInvalid() { return this.form.get('claimed_source')?.invalid && this.form.get('claimed_source')?.touched; }

  onSubmit(): void {
    if (this.form.invalid) { this.form.markAllAsTouched(); return; }
    this.loading = true;

    const payload: any = {
      headline: this.form.value.headline,
      claimed_source: this.form.value.claimed_source,
    };
    if (this.form.value.body?.trim()) payload.body = this.form.value.body;

    this.api.post<VerificationResult>(API_ENDPOINTS.VERIFICATION, payload).subscribe({
      next: (result) => {
        this.router.navigate(['/verify', result.claim_id]);
      },
      error: (err) => {
        this.loading = false;
        const msg = err.error?.message || 'Verification failed. Please try again.';
        this.toast.error(msg);
      },
    });
  }
}
