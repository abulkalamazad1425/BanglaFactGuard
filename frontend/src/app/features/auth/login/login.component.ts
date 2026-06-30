import { Component, inject } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterLink, ActivatedRoute } from '@angular/router';
import { CommonModule } from '@angular/common';
import { AuthService } from '../../../core/services/auth.service';
import { ToastService } from '../../../shared/services/toast.service';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, RouterLink],
  template: `
    <div class="auth-card glass-card animate-scale">
      <div class="auth-header">
        <h1>Welcome back</h1>
        <p>Sign in to your BanglaFactGuard account</p>
      </div>

      <form [formGroup]="form" (ngSubmit)="onSubmit()" class="auth-form">
        <div class="form-group">
          <label class="form-label">Email address</label>
          <input type="email" formControlName="email"
                 class="form-control"
                 [class.is-invalid]="emailInvalid"
                 placeholder="you@example.com"
                 autocomplete="email" />
          @if (emailInvalid) {
            <span class="form-error">Please enter a valid email address</span>
          }
        </div>

        <div class="form-group">
          <label class="form-label">Password</label>
          <div class="password-wrap">
            <input [type]="showPassword ? 'text' : 'password'"
                   formControlName="password"
                   class="form-control"
                   [class.is-invalid]="passwordInvalid"
                   placeholder="Your password"
                   autocomplete="current-password" />
            <button type="button" class="password-toggle" (click)="showPassword = !showPassword">
              {{ showPassword ? '🙈' : '👁️' }}
            </button>
          </div>
          @if (passwordInvalid) {
            <span class="form-error">Password is required</span>
          }
        </div>

        <div class="form-extras">
          <a routerLink="/auth/forgot-password" class="forgot-link">Forgot password?</a>
        </div>

        @if (errorMsg) {
          <div class="alert-error">{{ errorMsg }}</div>
        }

        <button type="submit" class="btn btn-primary btn-full btn-lg" [disabled]="loading">
          @if (loading) { <span class="btn-spinner"></span> }
          {{ loading ? 'Signing in...' : 'Sign In' }}
        </button>
      </form>

      <p class="auth-footer">
        Don't have an account? <a routerLink="/auth/register">Create one</a>
      </p>
    </div>
  `,
  styles: [`
    .auth-card {
      width: 100%;
      background: rgba(16,18,26,0.8);
      backdrop-filter: blur(24px);
    }
    .auth-header {
      text-align: center; margin-bottom: 32px;
      h1 { font-size: 1.75rem; margin-bottom: 8px; }
      p  { color: var(--text-secondary); font-size: 15px; }
    }
    .auth-form { display: flex; flex-direction: column; gap: 20px; }
    .form-extras { display: flex; justify-content: flex-end; }
    .forgot-link { font-size: 13px; color: var(--primary-light); }
    .password-wrap { position: relative; }
    .password-toggle {
      position: absolute; right: 12px; top: 50%; transform: translateY(-50%);
      background: none; border: none; cursor: pointer; font-size: 16px; padding: 0;
    }
    .password-wrap .form-control { padding-right: 44px; }
    .alert-error {
      padding: 12px 16px; background: var(--error-bg); border: 1px solid rgba(239,68,68,0.25);
      border-radius: var(--radius-md); color: var(--error); font-size: 14px;
    }
    .auth-footer {
      margin-top: 24px; text-align: center; font-size: 14px;
      color: var(--text-secondary);
      a { color: var(--primary-light); }
    }
    .btn-spinner {
      width: 16px; height: 16px;
      border: 2px solid rgba(255,255,255,0.3); border-top-color: white;
      border-radius: 50%; animation: spin 0.7s linear infinite;
    }
  `]
})
export class LoginComponent {
  private readonly fb = inject(FormBuilder);
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);
  private readonly toast = inject(ToastService);

  loading = false;
  showPassword = false;
  errorMsg = '';

  form = this.fb.group({
    email: ['', [Validators.required, Validators.email]],
    password: ['', Validators.required],
  });

  get emailInvalid() { return this.form.get('email')?.invalid && this.form.get('email')?.touched; }
  get passwordInvalid() { return this.form.get('password')?.invalid && this.form.get('password')?.touched; }

  onSubmit(): void {
    if (this.form.invalid) { this.form.markAllAsTouched(); return; }
    this.loading = true;
    this.errorMsg = '';

    const { email, password } = this.form.value;
    this.auth.login({ email: email!, password: password! }).subscribe({
      next: () => {
        this.toast.success('Welcome back!');
        const returnUrl = this.route.snapshot.queryParams['returnUrl'] || '/';
        this.router.navigate([returnUrl]);
      },
      error: (err) => {
        this.errorMsg = err.error?.message || 'Invalid email or password';
        this.loading = false;
      },
    });
  }
}
