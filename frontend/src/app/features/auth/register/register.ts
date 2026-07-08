import { Component, inject } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators, AbstractControl, ValidationErrors } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { CommonModule } from '@angular/common';
import { AuthService } from '../../../services/auth.service';
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
  templateUrl: './register.html',
  styleUrls: ['./register.scss']
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
      confirm: ['', Validators.required],
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
