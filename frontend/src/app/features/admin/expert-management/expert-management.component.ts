import { Component, OnInit, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ApiService } from '../../../core/services/api.service';
import { ToastService } from '../../../shared/services/toast.service';
import { ExpertResponse, CreateExpertRequest, UpdateExpertRequest } from '../../../core/models/admin.model';
import { API_ENDPOINTS } from '../../../core/constants/api-endpoints.constant';

@Component({
  selector: 'app-expert-management',
  standalone: true,
  imports: [CommonModule, RouterLink, ReactiveFormsModule],
  template: `
    <div class="mgmt-page">
      <div class="container" style="padding-top:48px; padding-bottom:80px;">
        <div class="page-header animate-in">
          <div class="header-content">
            <div>
              <h1>Expert Management</h1>
              <p>Manage expert reviewer accounts</p>
            </div>
            <a routerLink="/admin/experts/new" class="btn btn-primary">+ Create Expert</a>
          </div>
        </div>

        @if (loading()) { <div class="loading-overlay"><div class="spinner"></div></div> }

        @if (!loading()) {
          <div class="table-card card animate-in">
            <table class="data-table">
              <thead><tr>
                <th>Name</th>
                <th>Email</th>
                <th>Expertise</th>
                <th>Credibility</th>
                <th>Votes</th>
                <th>Status</th>
                <th>Actions</th>
              </tr></thead>
              <tbody>
                @for (exp of experts(); track exp.id) {
                  <tr>
                    <td class="font-semibold">{{ exp.full_name || '—' }}</td>
                    <td class="text-muted text-sm">{{ exp.email }}</td>
                    <td class="text-muted text-sm">{{ exp.expertise_area || '—' }}</td>
                    <td>
                      @if (exp.credibility_score !== null) {
                        <span [style.color]="credColor(exp.credibility_score!)">
                          {{ (exp.credibility_score! * 100).toFixed(1) }}%
                        </span>
                      } @else { <span class="text-muted">—</span> }
                    </td>
                    <td>{{ exp.total_votes }}</td>
                    <td>
                      <span class="badge" [class]="exp.is_active ? 'badge-true' : 'badge-false'">
                        {{ exp.is_active ? 'Active' : 'Inactive' }}
                      </span>
                    </td>
                    <td>
                      <div class="action-btns">
                        @if (exp.is_active) {
                          <button class="btn btn-danger btn-sm" (click)="deactivate(exp)">Deactivate</button>
                        } @else {
                          <button class="btn btn-secondary btn-sm" (click)="activate(exp)">Activate</button>
                        }
                        <button class="btn btn-ghost btn-sm" (click)="resetPwd(exp)">Reset Pwd</button>
                      </div>
                    </td>
                  </tr>
                }
                @empty {
                  <tr><td colspan="7" class="text-center text-muted" style="padding:40px;">No experts found.</td></tr>
                }
              </tbody>
            </table>
          </div>

          <!-- Reset password dialog -->
          @if (resetTarget()) {
            <div class="modal-overlay" (click)="resetTarget.set(null)">
              <div class="modal-card card" (click)="$event.stopPropagation()">
                <h3>Reset Password for {{ resetTarget()!.full_name }}</h3>
                <form [formGroup]="pwForm" (ngSubmit)="confirmReset()" style="margin-top:20px;">
                  <div class="form-group">
                    <label class="form-label">New Password</label>
                    <input type="password" formControlName="password" class="form-control" placeholder="Min 8 chars, 1 uppercase, 1 digit" />
                  </div>
                  <div class="modal-actions">
                    <button type="button" class="btn btn-ghost" (click)="resetTarget.set(null)">Cancel</button>
                    <button type="submit" class="btn btn-primary" [disabled]="pwForm.invalid || resetting()">
                      {{ resetting() ? 'Resetting...' : 'Reset Password' }}
                    </button>
                  </div>
                </form>
              </div>
            </div>
          }
        }
      </div>
    </div>
  `,
  styles: [`
    .mgmt-page { background: var(--bg-base); min-height: 100%; }
    .page-header { margin-bottom: 32px; }
    .header-content { display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 16px; h1 { margin-bottom: 8px; } p { color: var(--text-secondary); } }
    .table-card { padding: 0; overflow: hidden; }
    .action-btns { display: flex; gap: 8px; flex-wrap: wrap; }
    .modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.6); z-index: 200; display: flex; align-items: center; justify-content: center; padding: 24px; }
    .modal-card { max-width: 420px; width: 100%; h3 { font-size: 1.1rem; } }
    .form-group { margin-bottom: 20px; }
    .modal-actions { display: flex; justify-content: flex-end; gap: 12px; }
    .loading-overlay { display: flex; justify-content: center; padding: 80px; }
  `]
})
export class ExpertManagementComponent implements OnInit {
  private readonly api = inject(ApiService);
  private readonly toast = inject(ToastService);
  private readonly fb = inject(FormBuilder);

  readonly loading = signal(true);
  readonly experts = signal<ExpertResponse[]>([]);
  readonly resetTarget = signal<ExpertResponse | null>(null);
  readonly resetting = signal(false);

  pwForm = this.fb.group({ password: ['', [Validators.required, Validators.minLength(8)]] });

  credColor = (s: number) => s >= 0.7 ? 'var(--success)' : s >= 0.4 ? 'var(--warning)' : 'var(--error)';

  ngOnInit(): void {
    this.api.get<ExpertResponse[]>(API_ENDPOINTS.ADMIN_EXPERTS).subscribe({
      next: e => { this.experts.set(e); this.loading.set(false); },
      error: () => this.loading.set(false),
    });
  }

  deactivate(exp: ExpertResponse): void {
    this.api.post(`${API_ENDPOINTS.ADMIN_EXPERTS}/${exp.id}/deactivate`, {}).subscribe({
      next: (updated: any) => { this.experts.update(list => list.map(e => e.id === exp.id ? updated : e)); this.toast.success('Expert deactivated.'); },
      error: () => this.toast.error('Failed to deactivate expert.'),
    });
  }

  activate(exp: ExpertResponse): void {
    this.api.post(`${API_ENDPOINTS.ADMIN_EXPERTS}/${exp.id}/activate`, {}).subscribe({
      next: (updated: any) => { this.experts.update(list => list.map(e => e.id === exp.id ? updated : e)); this.toast.success('Expert activated.'); },
      error: () => this.toast.error('Failed to activate expert.'),
    });
  }

  resetPwd(exp: ExpertResponse): void { this.resetTarget.set(exp); this.pwForm.reset(); }

  confirmReset(): void {
    if (this.pwForm.invalid) return;
    this.resetting.set(true);
    this.api.post(`${API_ENDPOINTS.ADMIN_EXPERTS}/${this.resetTarget()!.id}/reset-password`, {
      new_password: this.pwForm.value.password,
    }).subscribe({
      next: () => { this.resetting.set(false); this.resetTarget.set(null); this.toast.success('Password reset successfully.'); },
      error: () => { this.resetting.set(false); this.toast.error('Failed to reset password.'); },
    });
  }
}
