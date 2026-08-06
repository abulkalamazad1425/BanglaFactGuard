import { Component, OnInit, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { FormBuilder, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { AdminService } from '../../../services/admin.service';
import { CredibilityWeightTier } from '../../../models/admin.model';
import { ToastService } from '../../../shared/services/toast.service';

@Component({
  selector: 'app-credibility-tiers',
  standalone: true,
  imports: [CommonModule, RouterLink, ReactiveFormsModule],
  templateUrl: './credibility-tiers.html',
  styleUrls: ['./credibility-tiers.scss']
})
export class CredibilityTiersComponent implements OnInit {
  private readonly adminSvc = inject(AdminService);
  private readonly toast = inject(ToastService);
  private readonly fb = inject(FormBuilder);

  readonly loading = signal(true);
  readonly saving = signal(false);
  readonly tiers = signal<CredibilityWeightTier[]>([]);

  drawerOpen = signal(false);
  isEditMode = signal(false);
  editingTierId: string | null = null;

  form: FormGroup = this.fb.group({
    label: ['', Validators.required],
    min_accuracy_pct: [0, [Validators.required, Validators.min(0), Validators.max(100)]],
    max_accuracy_pct: [100, [Validators.required, Validators.min(0), Validators.max(100)]],
    weight: [1.0, [Validators.required, Validators.min(0.01)]],
    is_active: [true],
  });

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.loading.set(true);
    this.adminSvc.listCredibilityTiers().subscribe({
      next: t => { this.tiers.set(t); this.loading.set(false); },
      error: () => { this.loading.set(false); this.toast.error('Failed to load credibility tiers.'); },
    });
  }

  openCreateDrawer(): void {
    this.isEditMode.set(false);
    this.editingTierId = null;
    this.form.reset({ label: '', min_accuracy_pct: 0, max_accuracy_pct: 100, weight: 1.0, is_active: true });
    this.drawerOpen.set(true);
  }

  openEditDrawer(tier: CredibilityWeightTier): void {
    this.isEditMode.set(true);
    this.editingTierId = tier.id;
    this.form.patchValue(tier);
    this.drawerOpen.set(true);
  }

  closeDrawer(): void {
    this.drawerOpen.set(false);
  }

  onSubmit(): void {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      this.toast.error('Please fix the validation errors.');
      return;
    }
    this.saving.set(true);
    const raw = this.form.value;
    const request = this.isEditMode()
      ? this.adminSvc.updateCredibilityTier(this.editingTierId!, raw)
      : this.adminSvc.createCredibilityTier(raw);

    request.subscribe({
      next: () => {
        this.toast.success(`Tier ${this.isEditMode() ? 'updated' : 'created'} successfully!`);
        this.saving.set(false);
        this.drawerOpen.set(false);
        this.load();
      },
      error: (err) => {
        this.toast.error(err.error?.detail?.message || err.error?.message || 'An error occurred.');
        this.saving.set(false);
      },
    });
  }

  deleteTier(tier: CredibilityWeightTier): void {
    if (!confirm(`Delete tier "${tier.label}"? This cannot be undone.`)) return;
    this.adminSvc.deleteCredibilityTier(tier.id).subscribe({
      next: () => { this.toast.success('Tier deleted.'); this.load(); },
      error: () => this.toast.error('Failed to delete tier.'),
    });
  }
}
