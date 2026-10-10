import { Component, OnInit, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { FormArray, FormBuilder, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { AdminService } from '../../../services/admin.service';
import { CredibilityWeightTier, CredibilityWeightTierItem } from '../../../models/admin.model';
import { ToastService } from '../../../shared/services/toast.service';

@Component({
  selector: 'app-credibility-tiers',
  standalone: true,
  imports: [CommonModule, RouterLink, ReactiveFormsModule],
  templateUrl: './credibility-tiers.html',
  styleUrls: ['./credibility-tiers.scss'],
})
export class CredibilityTiersComponent implements OnInit {
  private readonly adminSvc = inject(AdminService);
  private readonly toast = inject(ToastService);
  private readonly fb = inject(FormBuilder);

  readonly loading = signal(true);
  readonly saving = signal(false);
  readonly tiers = signal<CredibilityWeightTier[]>([]);

  readonly votingConfigSaving = signal(false);

  votingConfigForm: FormGroup = this.fb.group({
    min_expert_votes: [3, [Validators.required, Validators.min(1), Validators.max(50)]],
    activation_threshold_votes: [10, [Validators.required, Validators.min(0)]],
    verified_threshold: [5.0, [Validators.required, Validators.min(0.01)]],
    lead_margin: [1.0, [Validators.required, Validators.min(0)]],
    max_review_votes: [null as number | null, [Validators.min(1)]],
    max_review_hours: [null as number | null, [Validators.min(1)]],
  });

  /** The whole tier set, edited in place and saved together, so tiers can be
   *  split, merged or re-bounded without passing through an invalid state. */
  tiersForm: FormArray<FormGroup> = this.fb.array<FormGroup>([]);

  ngOnInit(): void {
    this.load();
    this.adminSvc.getVotingConfig().subscribe({
      next: (c) => this.votingConfigForm.patchValue(c),
      error: () => this.toast.error('Failed to load voting configuration.'),
    });
  }

  saveVotingConfig(): void {
    if (this.votingConfigForm.invalid) {
      this.votingConfigForm.markAllAsTouched();
      this.toast.error('Please fix the validation errors.');
      return;
    }
    this.votingConfigSaving.set(true);
    this.adminSvc.updateVotingConfig(this.votingConfigForm.value).subscribe({
      next: (c) => {
        this.votingConfigForm.patchValue(c);
        this.votingConfigSaving.set(false);
        this.toast.success('Voting configuration updated.');
      },
      error: (err) => {
        this.votingConfigSaving.set(false);
        this.toast.error(
          err.error?.detail?.message ||
            err.error?.message ||
            'Failed to update voting configuration.',
        );
      },
    });
  }

  load(): void {
    this.loading.set(true);
    this.adminSvc.listCredibilityTiers().subscribe({
      next: (t) => {
        this.setTiers(t);
        this.loading.set(false);
      },
      error: () => {
        this.loading.set(false);
        this.toast.error('Failed to load credibility tiers.');
      },
    });
  }

  private setTiers(tiers: CredibilityWeightTier[]): void {
    this.tiers.set(tiers);
    this.tiersForm.clear();
    tiers.forEach((t) => this.tiersForm.push(this.tierGroup(t)));
    this.tiersForm.markAsPristine();
  }

  private tierGroup(t: Partial<CredibilityWeightTierItem> = {}): FormGroup {
    return this.fb.group({
      id: [t.id ?? null],
      label: [t.label ?? '', [Validators.required, Validators.maxLength(100)]],
      min_accuracy_pct: [
        t.min_accuracy_pct ?? 0,
        [Validators.required, Validators.min(0), Validators.max(100)],
      ],
      max_accuracy_pct: [
        t.max_accuracy_pct ?? 100,
        [Validators.required, Validators.min(0), Validators.max(100)],
      ],
      weight: [t.weight ?? 1.0, [Validators.required, Validators.min(0.01)]],
      is_active: [t.is_active ?? true],
    });
  }

  addTier(): void {
    this.tiersForm.push(this.tierGroup());
    this.tiersForm.markAsDirty();
  }

  removeTier(index: number): void {
    this.tiersForm.removeAt(index);
    this.tiersForm.markAsDirty();
  }

  discardChanges(): void {
    this.setTiers(this.tiers());
  }

  saveTiers(): void {
    if (this.tiersForm.invalid) {
      this.tiersForm.markAllAsTouched();
      this.toast.error('Please fix the validation errors.');
      return;
    }
    this.saving.set(true);
    const tiers = this.tiersForm.getRawValue() as CredibilityWeightTierItem[];
    this.adminSvc.saveCredibilityTiers(tiers).subscribe({
      next: (saved) => {
        this.setTiers(saved);
        this.saving.set(false);
        this.toast.success('Credibility tiers saved.');
      },
      error: (err) => {
        // Nothing is saved unless the active tiers cover 0–100% exactly.
        this.saving.set(false);
        this.toast.error(
          err.error?.detail?.message || err.error?.message || 'Failed to save credibility tiers.',
        );
      },
    });
  }
}
