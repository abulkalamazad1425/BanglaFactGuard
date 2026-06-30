import { Component, OnInit, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { CommonModule } from '@angular/common';
import { ApiService } from '../../../core/services/api.service';
import { AuthService } from '../../../core/services/auth.service';
import { ToastService } from '../../../shared/services/toast.service';
import { UserProfile, UpdateProfileRequest } from '../../../core/models/user.model';
import { API_ENDPOINTS } from '../../../core/constants/api-endpoints.constant';

@Component({
  selector: 'app-profile-settings',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule],
  template: `
    <div class="settings-page">
      <div class="container container-sm" style="padding-top:48px; padding-bottom:80px;">
        <div class="page-header animate-in">
          <h1>Account Settings</h1>
          <p>Manage your profile and security settings</p>
        </div>

        <!-- Profile Section -->
        <div class="card settings-card animate-in">
          <h2 class="section-title">Profile Information</h2>
          <div class="profile-avatar">
            <div class="avatar-lg">{{ initial() }}</div>
            <div>
              <p class="font-semibold">{{ auth.user()?.full_name || 'No name set' }}</p>
              <p class="text-muted text-sm">{{ auth.user()?.email }}</p>
              <span class="badge badge-primary">{{ auth.user()?.role }}</span>
            </div>
          </div>

          <form [formGroup]="profileForm" (ngSubmit)="saveProfile()" style="margin-top:24px;">
            <div class="form-group">
              <label class="form-label">Full Name</label>
              <input type="text" formControlName="full_name" class="form-control" placeholder="Your full name" />
            </div>
            <div class="form-group">
              <label class="form-label">Bio <span class="text-muted text-xs">(optional)</span></label>
              <textarea formControlName="bio" class="form-control" rows="3" placeholder="Tell us about yourself..."></textarea>
            </div>
            <button type="submit" class="btn btn-primary" [disabled]="savingProfile()">
              @if (savingProfile()) { <span class="btn-spinner"></span> }
              {{ savingProfile() ? 'Saving...' : 'Save Profile' }}
            </button>
          </form>
        </div>

        <!-- Change Password Section -->
        <div class="card settings-card animate-in" style="margin-top:24px; animation-delay:0.1s;">
          <h2 class="section-title">Change Password</h2>
          <form [formGroup]="pwForm" (ngSubmit)="changePassword()">
            <div class="form-group">
              <label class="form-label">Current Password</label>
              <input type="password" formControlName="current_password" class="form-control"
                     [class.is-invalid]="pwForm.get('current_password')?.invalid && pwForm.get('current_password')?.touched"
                     placeholder="Your current password" />
            </div>
            <div class="form-group">
              <label class="form-label">New Password</label>
              <input type="password" formControlName="new_password" class="form-control"
                     [class.is-invalid]="pwForm.get('new_password')?.invalid && pwForm.get('new_password')?.touched"
                     placeholder="Min 8 chars, 1 uppercase, 1 digit" />
            </div>
            <button type="submit" class="btn btn-secondary" [disabled]="changingPw()">
              @if (changingPw()) { <span class="btn-spinner"></span> }
              {{ changingPw() ? 'Changing...' : 'Change Password' }}
            </button>
          </form>
        </div>

        <!-- Account Info -->
        <div class="card settings-card animate-in" style="margin-top:24px; animation-delay:0.2s;">
          <h2 class="section-title">Account Information</h2>
          <div class="info-list-items">
            <div class="info-row">
              <span class="info-key">Account ID</span>
              <span class="info-val font-medium" style="font-family:monospace; font-size:13px;">{{ auth.user()?.id }}</span>
            </div>
            <div class="info-row">
              <span class="info-key">Role</span>
              <span class="badge badge-primary">{{ auth.user()?.role }}</span>
            </div>
            <div class="info-row">
              <span class="info-key">Verification Status</span>
              <span class="badge" [class]="auth.user()?.is_verified ? 'badge-true' : 'badge-not-found'">
                {{ auth.user()?.is_verified ? 'Verified' : 'Unverified' }}
              </span>
            </div>
            <div class="info-row">
              <span class="info-key">Account Status</span>
              <span class="badge" [class]="auth.user()?.is_active ? 'badge-true' : 'badge-false'">
                {{ auth.user()?.is_active ? 'Active' : 'Inactive' }}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .settings-page { background: var(--bg-base); min-height: 100%; }
    .page-header { margin-bottom: 32px; h1 { margin-bottom: 8px; } p { color: var(--text-secondary); } }
    .settings-card { padding: 32px; }
    .section-title { font-size: 1rem; margin-bottom: 24px; padding-bottom: 16px; border-bottom: 1px solid var(--border); }
    .profile-avatar { display: flex; align-items: center; gap: 20px; }
    .avatar-lg {
      width: 64px; height: 64px; border-radius: 50%;
      background: var(--gradient-primary);
      display: flex; align-items: center; justify-content: center;
      font-size: 24px; font-weight: 700; color: white; flex-shrink: 0;
    }
    .form-group { margin-bottom: 20px; }
    .info-list-items { display: flex; flex-direction: column; gap: 0; }
    .info-row { display: flex; align-items: center; justify-content: space-between; padding: 14px 0; border-bottom: 1px solid var(--border); &:last-child { border-bottom: none; } }
    .info-key { font-size: 14px; color: var(--text-secondary); }
    .info-val { font-size: 14px; }
    .btn-spinner { width: 16px; height: 16px; border: 2px solid rgba(255,255,255,0.3); border-top-color: white; border-radius: 50%; animation: spin 0.7s linear infinite; }
  `]
})
export class ProfileSettingsComponent implements OnInit {
  readonly auth = inject(AuthService);
  private readonly api = inject(ApiService);
  private readonly toast = inject(ToastService);
  private readonly fb = inject(FormBuilder);

  readonly savingProfile = signal(false);
  readonly changingPw = signal(false);

  initial = () => (this.auth.user()?.full_name || this.auth.user()?.email || 'U').charAt(0).toUpperCase();

  profileForm = this.fb.group({
    full_name: [''],
    bio: [''],
  });

  pwForm = this.fb.group({
    current_password: ['', Validators.required],
    new_password: ['', [Validators.required, Validators.minLength(8), Validators.pattern(/^(?=.*[A-Z])(?=.*\d).+$/)]],
  });

  ngOnInit(): void {
    const user = this.auth.user();
    if (user) {
      this.profileForm.patchValue({ full_name: user.full_name || '' });
    }
    this.api.get<UserProfile>(API_ENDPOINTS.USERS_PROFILE).subscribe({
      next: p => this.profileForm.patchValue({ full_name: p.full_name || '', bio: p.bio || '' }),
      error: () => {},
    });
  }

  saveProfile(): void {
    this.savingProfile.set(true);
    this.api.patch<UserProfile>(API_ENDPOINTS.USERS_PROFILE, this.profileForm.value).subscribe({
      next: () => { this.savingProfile.set(false); this.toast.success('Profile updated.'); this.auth.loadCurrentUser().subscribe(); },
      error: () => { this.savingProfile.set(false); this.toast.error('Failed to update profile.'); },
    });
  }

  changePassword(): void {
    if (this.pwForm.invalid) { this.pwForm.markAllAsTouched(); return; }
    this.changingPw.set(true);
    const { current_password, new_password } = this.pwForm.value;
    this.auth.changePassword(current_password!, new_password!).subscribe({
      next: () => { this.changingPw.set(false); this.toast.success('Password changed successfully.'); this.pwForm.reset(); },
      error: err => { this.changingPw.set(false); this.toast.error(err.error?.message || 'Failed to change password.'); },
    });
  }
}
