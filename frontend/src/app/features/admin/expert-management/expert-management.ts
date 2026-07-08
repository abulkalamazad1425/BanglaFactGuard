import { Component, OnInit, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { AdminService } from '../../../services/admin.service';
import { ToastService } from '../../../shared/services/toast.service';
import { ExpertResponse, CreateExpertRequest, UpdateExpertRequest } from '../../../models/admin.model';

@Component({
  selector: 'app-expert-management',
  standalone: true,
  imports: [CommonModule, RouterLink, ReactiveFormsModule],
  templateUrl: './expert-management.html',
  styleUrls: ['./expert-management.scss']
})
export class ExpertManagementComponent implements OnInit {
  private readonly adminSvc = inject(AdminService);
  private readonly toast = inject(ToastService);
  private readonly fb = inject(FormBuilder);

  readonly loading = signal(true);
  readonly experts = signal<ExpertResponse[]>([]);
  readonly resetTarget = signal<ExpertResponse | null>(null);
  readonly resetting = signal(false);

  pwForm = this.fb.group({ password: ['', [Validators.required, Validators.minLength(8)]] });

  credColor = (s: number) => s >= 0.7 ? 'var(--success)' : s >= 0.4 ? 'var(--warning)' : 'var(--error)';

  ngOnInit(): void {
    this.adminSvc.listExperts().subscribe({
      next: e => { this.experts.set(e); this.loading.set(false); },
      error: () => this.loading.set(false),
    });
  }

  deactivate(exp: ExpertResponse): void {
    this.adminSvc.deactivateExpert(exp.id).subscribe({
      next: (updated: any) => { this.experts.update(list => list.map(e => e.id === exp.id ? updated : e)); this.toast.success('Expert deactivated.'); },
      error: () => this.toast.error('Failed to deactivate expert.'),
    });
  }

  activate(exp: ExpertResponse): void {
    this.adminSvc.activateExpert(exp.id).subscribe({
      next: (updated: any) => { this.experts.update(list => list.map(e => e.id === exp.id ? updated : e)); this.toast.success('Expert activated.'); },
      error: () => this.toast.error('Failed to activate expert.'),
    });
  }

  resetPwd(exp: ExpertResponse): void { this.resetTarget.set(exp); this.pwForm.reset(); }

  confirmReset(): void {
    if (this.pwForm.invalid) return;
    this.resetting.set(true);
    this.adminSvc.resetExpertPassword(this.resetTarget()!.id, {
      new_password: this.pwForm.value.password as string,
    }).subscribe({
      next: () => { this.resetting.set(false); this.resetTarget.set(null); this.toast.success('Password reset successfully.'); },
      error: () => { this.resetting.set(false); this.toast.error('Failed to reset password.'); },
    });
  }
}
