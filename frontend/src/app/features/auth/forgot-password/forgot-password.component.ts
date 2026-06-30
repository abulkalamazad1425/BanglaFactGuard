import { Component, inject } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { AuthService } from '../../../core/services/auth.service';

@Component({
  selector: 'app-forgot-password',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, RouterLink],
  template: `
    <div class="auth-card glass-card animate-scale">
      @if (!sent) {
        <div class="auth-header">
          <h1>Reset password</h1>
          <p>Enter your email and we'll log the reset token</p>
        </div>
        <form [formGroup]="form" (ngSubmit)="onSubmit()" class="auth-form">
          <div class="form-group">
            <label class="form-label">Email address</label>
            <input type="email" formControlName="email" class="form-control"
                   [class.is-invalid]="invalid" placeholder="you@example.com" />
            @if (invalid) { <span class="form-error">Valid email required</span> }
          </div>
          <button type="submit" class="btn btn-primary btn-full btn-lg" [disabled]="loading">
            @if (loading) { <span class="btn-spinner"></span> }
            {{ loading ? 'Sending...' : 'Send Reset Link' }}
          </button>
        </form>
      } @else {
        <div class="success-state">
          <div class="success-icon">📧</div>
          <h2>Check your email</h2>
          <p>If that email is registered, a reset link has been sent. In development mode, the token is logged in the backend console.</p>
          <a routerLink="/auth/login" class="btn btn-primary btn-full mt-4">Back to Login</a>
        </div>
      }
      <p class="auth-footer"><a routerLink="/auth/login">← Back to login</a></p>
    </div>
  `,
  styles: [`
    .auth-card { width: 100%; background: rgba(16,18,26,0.8); backdrop-filter: blur(24px); }
    .auth-header { text-align: center; margin-bottom: 32px; h1 { font-size: 1.75rem; margin-bottom: 8px; } p { color: var(--text-secondary); } }
    .auth-form { display: flex; flex-direction: column; gap: 20px; }
    .auth-footer { margin-top: 24px; text-align: center; font-size: 14px; a { color: var(--primary-light); } }
    .success-state { text-align: center; padding: 16px 0; }
    .success-icon { font-size: 56px; margin-bottom: 20px; }
    .btn-spinner { width: 16px; height: 16px; border: 2px solid rgba(255,255,255,0.3); border-top-color: white; border-radius: 50%; animation: spin 0.7s linear infinite; }
  `]
})
export class ForgotPasswordComponent {
  private readonly fb = inject(FormBuilder);
  private readonly auth = inject(AuthService);

  loading = false;
  sent = false;

  form = this.fb.group({
    email: ['', [Validators.required, Validators.email]],
  });

  get invalid() { return this.form.get('email')?.invalid && this.form.get('email')?.touched; }

  onSubmit(): void {
    if (this.form.invalid) { this.form.markAllAsTouched(); return; }
    this.loading = true;
    this.auth.requestPasswordReset(this.form.value.email!).subscribe({
      next: () => { this.sent = true; this.loading = false; },
      error: () => { this.sent = true; this.loading = false; }, // always show success
    });
  }
}
