import { Component, inject } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators, AbstractControl, ValidationErrors } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { CommonModule } from '@angular/common';
import { AuthService } from '../../../core/services/auth.service';
import { ToastService } from '../../../shared/services/toast.service';

function passwordStrength(ctrl: AbstractControl): ValidationErrors | null {
  const v = ctrl.value || '';
  if (v.length < 8) return { weakPassword: 'At least 8 characters' };
  if (!/\d/.test(v)) return { weakPassword: 'Must contain a digit' };
  if (!/[A-Z]/.test(v)) return { weakPassword: 'Must contain an uppercase letter' };
  return null;
}

function passwordMatch(group: AbstractControl): ValidationErrors | null {
  const pw = group.get('password')?.value;
  const confirm = group.get('confirm')?.value;
  return pw && confirm && pw !== confirm ? { mismatch: true } : null;
}

@Component({
  selector: 'app-register',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, RouterLink],
  template: `
    <div class="auth-card glass-card animate-scale">
      <div class="auth-header">
        <h1>Create account</h1>
        <p>Join BanglaFactGuard to track your verifications</p>
      </div>

      <form [formGroup]="form" (ngSubmit)="onSubmit()" class="auth-form">
        <div class="form-group">
          <label class="form-label">Full Name</label>
          <input type="text" formControlName="full_name" class="form-control"
                 placeholder="Your full name" autocomplete="name" />
        </div>

        <div class="form-group">
          <label class="form-label">Email address</label>
          <input type="email" formControlName="email"
                 class="form-control"
                 [class.is-invalid]="emailInvalid"
                 placeholder="you@example.com" />
          @if (emailInvalid) {
            <span class="form-error">Valid email is required</span>
          }
        </div>

        <div class="form-group" formGroupName="passwords">
          <label class="form-label">Password</label>
          <input type="password" formControlName="password"
                 class="form-control"
                 [class.is-invalid]="pwInvalid"
                 placeholder="Min 8 chars, 1 uppercase, 1 digit" />
          @if (pwError) {
            <span class="form-error">{{ pwError }}</span>
          }
        </div>

        <div class="form-group" formGroupName="passwords">
          <label class="form-label">Confirm Password</label>
          <input type="password" formControlName="confirm"
                 class="form-control"
                 [class.is-invalid]="confirmInvalid"
                 placeholder="Repeat your password" />
          @if (confirmInvalid) {
            <span class="form-error">Passwords do not match</span>
          }
        </div>

        @if (errorMsg) {
          <div class="alert-error">{{ errorMsg }}</div>
        }

        <button type="submit" class="btn btn-primary btn-full btn-lg" [disabled]="loading">
          @if (loading) { <span class="btn-spinner"></span> }
          {{ loading ? 'Creating account...' : 'Create Account' }}
        </button>
      </form>

      <p class="auth-footer">
        Already have an account? <a routerLink="/auth/login">Sign in</a>
      </p>
    </div>
  `,
  styles: [`
    .auth-card { width: 100%; background: rgba(16,18,26,0.8); backdrop-filter: blur(24px); }
    .auth-header { text-align: center; margin-bottom: 32px; h1 { font-size: 1.75rem; margin-bottom: 8px; } p { color: var(--text-secondary); } }
    .auth-form { display: flex; flex-direction: column; gap: 20px; }
    .alert-error { padding: 12px 16px; background: var(--error-bg); border: 1px solid rgba(239,68,68,0.25); border-radius: var(--radius-md); color: var(--error); font-size: 14px; }
    .auth-footer { margin-top: 24px; text-align: center; font-size: 14px; color: var(--text-secondary); a { color: var(--primary-light); } }
    .btn-spinner { width: 16px; height: 16px; border: 2px solid rgba(255,255,255,0.3); border-top-color: white; border-radius: 50%; animation: spin 0.7s linear infinite; }
  `]
})
export class RegisterComponent {
  private readonly fb = inject(FormBuilder);
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  private readonly toast = inject(ToastService);

  loading = false;
  errorMsg = '';

  form = this.fb.group({
    full_name: [''],
    email: ['', [Validators.required, Validators.email]],
    passwords: this.fb.group({
      password: ['', [Validators.required, passwordStrength]],
      confirm:  ['', Validators.required],
    }, { validators: passwordMatch }),
  });

  get emailInvalid() { return this.form.get('email')?.invalid && this.form.get('email')?.touched; }
  get pwGroup() { return this.form.get('passwords'); }
  get pwCtrl() { return this.pwGroup?.get('password'); }
  get pwInvalid() { return this.pwCtrl?.invalid && this.pwCtrl?.touched; }
  get pwError() { return this.pwCtrl?.errors?.['weakPassword'] as string | null; }
  get confirmCtrl() { return this.pwGroup?.get('confirm'); }
  get confirmInvalid() {
    return (this.pwGroup?.errors?.['mismatch'] && this.confirmCtrl?.touched) ||
           (this.confirmCtrl?.invalid && this.confirmCtrl?.touched);
  }

  onSubmit(): void {
    if (this.form.invalid) { this.form.markAllAsTouched(); return; }
    this.loading = true;
    this.errorMsg = '';

    const { full_name, email, passwords } = this.form.value;
    this.auth.register({
      email: email!,
      password: passwords!.password!,
      full_name: full_name || undefined,
    }).subscribe({
      next: () => {
        this.toast.success('Account created! Welcome to BanglaFactGuard.');
        this.router.navigate(['/']);
      },
      error: (err) => {
        this.errorMsg = err.error?.message || 'Registration failed. Please try again.';
        this.loading = false;
      },
    });
  }
}
