import { requestError } from '../../../shared/utils/presentation';
import { Component, OnInit, inject, signal, computed } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { CommonModule } from '@angular/common';
import { AuthService } from '../../../services/auth.service';
import { ExpertService } from '../../../services/expert.service';
import { ToastService } from '../../../shared/services/toast.service';
import { UserProfile } from '../../../models/user.model';
import { ExpertStats } from '../../../models/expert.model';

const RING_RADIUS = 52;

@Component({
  selector: 'app-profile-settings',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule],
  templateUrl: './profile-settings.html',
  styleUrls: ['./profile-settings.scss'],
})
export class ProfileSettingsComponent implements OnInit {
  readonly auth = inject(AuthService);
  private readonly expertSvc = inject(ExpertService);
  private readonly toast = inject(ToastService);
  private readonly fb = inject(FormBuilder);

  readonly profile = signal<UserProfile | null>(null);
  readonly profileError = signal(false);
  readonly savingProfile = signal(false);
  readonly changingPw = signal(false);
  readonly stats = signal<ExpertStats | null>(null);
  readonly statsError = signal(false);

  // Requirement 2.2: experts may VIEW their profile but never modify it.
  readonly isExpertOnly = computed(() => this.auth.user()?.role === 'expert');

  readonly displayName = computed(
    () =>
      this.profile()?.full_name ||
      this.auth.user()?.full_name ||
      this.auth.user()?.email?.split('@')[0] ||
      'User',
  );
  readonly initial = computed(() => this.displayName().charAt(0).toUpperCase());
  readonly roleLabel = computed(() => {
    const role = this.auth.user()?.role;
    return role === 'admin'
      ? 'Administrator'
      : role === 'expert'
        ? 'Expert reviewer'
        : 'Registered user';
  });

  readonly ringCircumference = 2 * Math.PI * RING_RADIUS;
  readonly ringRadius = RING_RADIUS;

  readonly credibilityActive = computed(() => this.stats()?.current_credibility != null);
  readonly ringFraction = computed(() => {
    const s = this.stats();
    if (!s) return 0;
    if (s.current_credibility != null) return s.current_credibility;
    return s.activation_threshold ? Math.min(s.total_votes / s.activation_threshold, 1) : 0;
  });
  readonly reviewsToActivate = computed(() => {
    const s = this.stats();
    return s ? Math.max(s.activation_threshold - s.total_votes, 0) : 0;
  });
  readonly scoreTone = computed(() => {
    if (!this.credibilityActive()) return 'pending';
    const v = this.stats()!.current_credibility!;
    return v >= 0.7 ? 'high' : v >= 0.4 ? 'mid' : 'low';
  });

  profileForm = this.fb.group({
    full_name: ['', [Validators.maxLength(255)]],
  });

  pwForm = this.fb.group({
    current_password: ['', Validators.required],
    new_password: [
      '',
      [Validators.required, Validators.minLength(8), Validators.pattern(/^(?=.*[A-Z])(?=.*\d).+$/)],
    ],
  });

  ngOnInit(): void {
    this.loadProfile();
    if (this.isExpertOnly()) this.loadStats();
  }

  loadProfile(): void {
    this.profileError.set(false);
    this.profileForm.patchValue({ full_name: this.auth.user()?.full_name || '' });
    this.auth.getProfile().subscribe({
      next: (p) => {
        this.profile.set(p);
        this.profileForm.patchValue({ full_name: p.full_name || '' });
      },
      error: () => this.profileError.set(true),
    });
  }

  loadStats(): void {
    this.statsError.set(false);
    this.expertSvc.getStats().subscribe({
      next: (s) => this.stats.set(s),
      error: () => this.statsError.set(true),
    });
  }

  saveProfile(): void {
    if (this.isExpertOnly() || this.profileForm.invalid) return;
    this.savingProfile.set(true);
    this.auth.updateProfile({ full_name: this.profileForm.value.full_name ?? '' }).subscribe({
      next: (p) => {
        this.profile.set(p);
        this.savingProfile.set(false);
        this.toast.success('Profile updated.');
      },
      error: () => {
        this.savingProfile.set(false);
        this.toast.error('Failed to update profile.');
      },
    });
  }

  changePassword(): void {
    if (this.pwForm.invalid) {
      this.pwForm.markAllAsTouched();
      return;
    }
    this.changingPw.set(true);
    const { current_password, new_password } = this.pwForm.value;
    this.auth.changePassword(current_password!, new_password!).subscribe({
      next: () => {
        this.changingPw.set(false);
        this.toast.success('Password changed successfully.');
        this.pwForm.reset();
      },
      error: (err) => {
        this.changingPw.set(false);
        this.toast.error(requestError(err, 'Failed to change password.'));
      },
    });
  }
}
