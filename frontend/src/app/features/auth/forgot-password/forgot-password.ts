import { Component, inject } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { CommonModule } from '@angular/common';
import { Router, RouterLink } from '@angular/router';
import { AuthService } from '../../../services/auth.service';
import { ToastService } from '../../../shared/services/toast.service';

type Step = 'request' | 'confirm';

@Component({
  selector: 'app-forgot-password',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, RouterLink],
  templateUrl: './forgot-password.html',
  styleUrls: ['./forgot-password.scss']
})
export class ForgotPasswordComponent {
  private readonly fb = inject(FormBuilder);
  private readonly auth = inject(AuthService);
  private readonly toast = inject(ToastService);
  private readonly router = inject(Router);

  step: Step = 'request';
  loading = false;
  submittedEmail = '';

  requestForm = this.fb.group({
    email: ['', [Validators.required, Validators.email]],
  });

  confirmForm = this.fb.group({
    otp: ['', [Validators.required, Validators.pattern(/^\d{4,10}$/)]],
    new_password: ['', [Validators.required, Validators.minLength(8), Validators.pattern(/^(?=.*[A-Z])(?=.*\d).+$/)]],
    confirm_password: ['', [Validators.required]],
  });

  get emailInvalid() { return this.requestForm.get('email')?.invalid && this.requestForm.get('email')?.touched; }
  get otpInvalid() { return this.confirmForm.get('otp')?.invalid && this.confirmForm.get('otp')?.touched; }
  get newPasswordInvalid() { return this.confirmForm.get('new_password')?.invalid && this.confirmForm.get('new_password')?.touched; }
  get passwordMismatch() {
    const { new_password, confirm_password } = this.confirmForm.value;
    return !!confirm_password && new_password !== confirm_password;
  }

  requestOtp(): void {
    if (this.requestForm.invalid) { this.requestForm.markAllAsTouched(); return; }
    this.loading = true;
    const email = this.requestForm.value.email!;
    this.auth.requestPasswordReset(email).subscribe({
      next: () => { this.submittedEmail = email; this.step = 'confirm'; this.loading = false; },
      error: () => { this.submittedEmail = email; this.step = 'confirm'; this.loading = false; }, // never reveal whether the email exists
    });
  }

  confirmReset(): void {
    if (this.confirmForm.invalid || this.passwordMismatch) {
      this.confirmForm.markAllAsTouched();
      return;
    }
    this.loading = true;
    const { otp, new_password } = this.confirmForm.value;
    this.auth.confirmPasswordReset(this.submittedEmail, otp!, new_password!).subscribe({
      next: () => {
        this.loading = false;
        this.toast.success('Password reset successfully. Please log in.');
        this.router.navigate(['/auth/login']);
      },
      error: (err) => {
        this.loading = false;
        this.toast.error(err.error?.detail?.message || err.error?.message || 'Invalid or expired code. Please try again.');
      },
    });
  }

  resendOtp(): void {
    if (!this.submittedEmail) return;
    this.auth.requestPasswordReset(this.submittedEmail).subscribe({ error: () => {} });
    this.toast.success('A new code has been sent if the email is registered.');
  }

  backToRequest(): void {
    this.step = 'request';
    this.confirmForm.reset();
  }
}
