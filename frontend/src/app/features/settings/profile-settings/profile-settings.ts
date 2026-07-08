import { Component, OnInit, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { CommonModule } from '@angular/common';
import { AuthService } from '../../../services/auth.service';
import { ToastService } from '../../../shared/services/toast.service';
import { UserProfile, UpdateProfileRequest } from '../../../models/user.model';

@Component({
  selector: 'app-profile-settings',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule],
  templateUrl: './profile-settings.html',
  styleUrls: ['./profile-settings.scss']
})
export class ProfileSettingsComponent implements OnInit {
  readonly auth = inject(AuthService);
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
    this.auth.getProfile().subscribe({
      next: p => this.profileForm.patchValue({ full_name: p.full_name || '', bio: p.bio || '' }),
      error: () => { },
    });
  }

  saveProfile(): void {
    this.savingProfile.set(true);
    const req: UpdateProfileRequest = {
      full_name: this.profileForm.value.full_name || undefined,
      bio: this.profileForm.value.bio || undefined,
    };
    this.auth.updateProfile(req).subscribe({
      next: () => { this.savingProfile.set(false); this.toast.success('Profile updated.'); },
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
