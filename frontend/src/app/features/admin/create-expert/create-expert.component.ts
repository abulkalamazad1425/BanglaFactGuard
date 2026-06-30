import { Component, inject } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { CommonModule } from '@angular/common';
import { ApiService } from '../../../core/services/api.service';
import { ToastService } from '../../../shared/services/toast.service';
import { API_ENDPOINTS } from '../../../core/constants/api-endpoints.constant';

@Component({
  selector: 'app-create-expert',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, RouterLink],
  template: `
    <div class="create-page">
      <div class="container container-sm" style="padding-top:48px; padding-bottom:80px;">
        <div class="topbar animate-in">
          <a routerLink="/admin/experts" class="btn btn-ghost btn-sm">← Back to Experts</a>
        </div>

        <div class="card animate-in" style="margin-top:16px; padding:40px;">
          <h1 style="font-size:1.5rem; margin-bottom:8px;">Create Expert Account</h1>
          <p class="text-muted" style="margin-bottom:32px;">The expert will receive credentials you provide. Encourage them to change their password upon first login.</p>

          <form [formGroup]="form" (ngSubmit)="onSubmit()">
            <div class="form-group">
              <label class="form-label">Full Name <span style="color:var(--error)">*</span></label>
              <input type="text" formControlName="full_name" class="form-control"
                     [class.is-invalid]="nameInvalid" placeholder="Dr. Example Name" />
              @if (nameInvalid) { <span class="form-error">Full name is required</span> }
            </div>
            <div class="form-group">
              <label class="form-label">Email Address <span style="color:var(--error)">*</span></label>
              <input type="email" formControlName="email" class="form-control"
                     [class.is-invalid]="emailInvalid" placeholder="expert@institution.edu" />
              @if (emailInvalid) { <span class="form-error">Valid email is required</span> }
            </div>
            <div class="form-group">
              <label class="form-label">Initial Password <span style="color:var(--error)">*</span></label>
              <input type="password" formControlName="password" class="form-control"
                     [class.is-invalid]="pwInvalid" placeholder="Min 8 chars, 1 uppercase, 1 digit" />
              @if (pwInvalid) { <span class="form-error">Strong password required (8+ chars, 1 uppercase, 1 digit)</span> }
            </div>
            <div class="form-group">
              <label class="form-label">Expertise Area <span style="color:var(--error)">*</span></label>
              <input type="text" formControlName="expertise_area" class="form-control"
                     [class.is-invalid]="areaInvalid" placeholder="e.g., Political Journalism, Health & Science" />
              @if (areaInvalid) { <span class="form-error">Expertise area is required</span> }
            </div>

            @if (errorMsg) {
              <div class="alert-error" style="margin-bottom:16px;">{{ errorMsg }}</div>
            }

            <div style="display:flex; gap:12px;">
              <a routerLink="/admin/experts" class="btn btn-ghost">Cancel</a>
              <button type="submit" class="btn btn-primary flex-1" [disabled]="loading">
                @if (loading) { <span class="btn-spinner"></span> Creating... }
                @else { ✅ Create Expert Account }
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .create-page { background: var(--bg-base); min-height: 100%; }
    .topbar { margin-bottom: 0; }
    .form-group { margin-bottom: 20px; }
    .alert-error { padding: 12px 16px; background: var(--error-bg); border: 1px solid rgba(239,68,68,0.25); border-radius: var(--radius-md); color: var(--error); font-size: 14px; }
    .btn-spinner { width: 16px; height: 16px; border: 2px solid rgba(255,255,255,0.3); border-top-color: white; border-radius: 50%; animation: spin 0.7s linear infinite; }
  `]
})
export class CreateExpertComponent {
  private readonly fb = inject(FormBuilder);
  private readonly api = inject(ApiService);
  private readonly router = inject(Router);
  private readonly toast = inject(ToastService);

  loading = false;
  errorMsg = '';

  form = this.fb.group({
    full_name: ['', Validators.required],
    email: ['', [Validators.required, Validators.email]],
    password: ['', [Validators.required, Validators.minLength(8), Validators.pattern(/^(?=.*[A-Z])(?=.*\d).+$/)]],
    expertise_area: ['', Validators.required],
  });

  get nameInvalid()  { return this.form.get('full_name')?.invalid && this.form.get('full_name')?.touched; }
  get emailInvalid() { return this.form.get('email')?.invalid && this.form.get('email')?.touched; }
  get pwInvalid()    { return this.form.get('password')?.invalid && this.form.get('password')?.touched; }
  get areaInvalid()  { return this.form.get('expertise_area')?.invalid && this.form.get('expertise_area')?.touched; }

  onSubmit(): void {
    if (this.form.invalid) { this.form.markAllAsTouched(); return; }
    this.loading = true; this.errorMsg = '';

    this.api.post(API_ENDPOINTS.ADMIN_EXPERTS, this.form.value).subscribe({
      next: () => { this.toast.success('Expert account created successfully.'); this.router.navigate(['/admin/experts']); },
      error: err => { this.errorMsg = err.error?.message || 'Failed to create expert.'; this.loading = false; },
    });
  }
}
