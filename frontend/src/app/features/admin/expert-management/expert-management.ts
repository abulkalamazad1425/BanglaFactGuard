import { Component, OnInit, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { Subscription } from 'rxjs';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { AdminService } from '../../../services/admin.service';
import { ToastService } from '../../../shared/services/toast.service';
import { ExpertResponse, UpdateExpertRequest } from '../../../models/admin.model';
import {
  PAGE_SIZE,
  PaginationComponent,
} from '../../../shared/components/pagination/pagination.component';

@Component({
  selector: 'app-expert-management',
  standalone: true,
  imports: [CommonModule, RouterLink, ReactiveFormsModule, PaginationComponent],
  templateUrl: './expert-management.html',
  styleUrls: ['./expert-management.scss'],
})
export class ExpertManagementComponent implements OnInit {
  private readonly adminSvc = inject(AdminService);
  private readonly toast = inject(ToastService);
  private readonly fb = inject(FormBuilder);

  readonly loading = signal(true);
  readonly loadError = signal(false);
  readonly busyId = signal<string | null>(null);
  readonly experts = signal<ExpertResponse[]>([]);
  readonly page = signal(1);
  readonly hasNext = signal(false);
  readonly limit = PAGE_SIZE;
  readonly resetTarget = signal<ExpertResponse | null>(null);
  readonly resetting = signal(false);
  readonly editTarget = signal<ExpertResponse | null>(null);
  readonly editing = signal(false);

  pwForm = this.fb.group({ password: ['', [Validators.required, Validators.minLength(8)]] });

  editForm = this.fb.group({
    full_name: ['', Validators.required],
    email: ['', [Validators.required, Validators.email]],
    expertise_area: [''],
  });

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.loading.set(true);
    this.loadError.set(false);
    // One extra row tells whether another page exists.
    // A newer search supersedes any request still in flight.
    this.request?.unsubscribe();
    this.request = this.adminSvc
      .listExperts(this.limit + 1, (this.page() - 1) * this.limit, this.query)
      .subscribe({
        next: (rows) => {
          this.hasNext.set(rows.length > this.limit);
          this.experts.set(rows.slice(0, this.limit));
          this.loading.set(false);
        },
        error: () => {
          this.loading.set(false);
          this.loadError.set(true);
        },
      });
  }

  goToPage(page: number): void {
    this.page.set(page);
    this.load();
  }

  /* ─── Search (name, email or expertise; server-side, before pagination) ─── */
  query = '';
  private searchTimer: ReturnType<typeof setTimeout> | null = null;
  private request?: Subscription;

  search(value: string): void {
    if (this.searchTimer) clearTimeout(this.searchTimer);
    this.query = value.trim();
    this.page.set(1);
    this.load();
  }

  /** Search as you type: ~300 ms after the last keystroke, first page. */
  onSearchInput(value: string): void {
    if (this.searchTimer) clearTimeout(this.searchTimer);
    this.searchTimer = setTimeout(() => {
      this.searchTimer = null;
      if (value.trim() !== this.query) this.search(value);
    }, 300);
  }

  /** Merge the server's answer into the existing row so a partial response
   *  can never blank a cell or reshape the table. */
  private applyUpdate(
    id: string,
    updated: Partial<ExpertResponse> | null | undefined,
    fallback: Partial<ExpertResponse>,
  ): void {
    this.experts.update((list) =>
      list.map((e) => (e.id === id ? { ...e, ...fallback, ...(updated ?? {}) } : e)),
    );
  }

  deactivate(exp: ExpertResponse): void {
    this.busyId.set(exp.id);
    this.adminSvc.deactivateExpert(exp.id).subscribe({
      next: (updated) => {
        this.applyUpdate(exp.id, updated, { is_active: false });
        this.busyId.set(null);
        this.toast.success('Expert deactivated.');
      },
      error: () => {
        this.busyId.set(null);
        this.toast.error('Failed to deactivate expert.');
      },
    });
  }

  activate(exp: ExpertResponse): void {
    this.busyId.set(exp.id);
    this.adminSvc.activateExpert(exp.id).subscribe({
      next: (updated) => {
        this.applyUpdate(exp.id, updated, { is_active: true });
        this.busyId.set(null);
        this.toast.success('Expert activated.');
      },
      error: () => {
        this.busyId.set(null);
        this.toast.error('Failed to activate expert.');
      },
    });
  }

  openEdit(exp: ExpertResponse): void {
    this.editTarget.set(exp);
    this.editForm.reset({
      full_name: exp.full_name || '',
      email: exp.email,
      expertise_area: exp.expertise_area || '',
    });
  }

  confirmEdit(): void {
    if (this.editForm.invalid) {
      this.editForm.markAllAsTouched();
      return;
    }
    this.editing.set(true);
    const body: UpdateExpertRequest = {
      full_name: this.editForm.value.full_name || undefined,
      email: this.editForm.value.email || undefined,
      expertise_area: this.editForm.value.expertise_area || undefined,
    };
    this.adminSvc.updateExpert(this.editTarget()!.id, body).subscribe({
      next: (updated) => {
        this.applyUpdate(updated.id, updated, {});
        this.editing.set(false);
        this.editTarget.set(null);
        this.toast.success('Expert account updated.');
      },
      error: (err) => {
        this.editing.set(false);
        this.toast.error(err.error?.detail?.message || 'Failed to update expert.');
      },
    });
  }

  resetPwd(exp: ExpertResponse): void {
    this.resetTarget.set(exp);
    this.pwForm.reset();
  }

  confirmReset(): void {
    if (this.pwForm.invalid) return;
    this.resetting.set(true);
    this.adminSvc
      .resetExpertPassword(this.resetTarget()!.id, {
        new_password: this.pwForm.value.password as string,
      })
      .subscribe({
        next: () => {
          this.resetting.set(false);
          this.resetTarget.set(null);
          this.toast.success('Password reset successfully.');
        },
        error: () => {
          this.resetting.set(false);
          this.toast.error('Failed to reset password.');
        },
      });
  }
}
