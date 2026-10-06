import { Component, OnInit, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { AdminService } from '../../../services/admin.service';
import { AdminDashboard, DashboardClaim } from '../../../models/admin.model';
import { OVERALL_LABELS } from '../../../shared/utils/status-labels';
import { OverallVerdict } from '../../../models/verification.model';

@Component({
  selector: 'app-admin-dashboard',
  standalone: true,
  imports: [CommonModule, RouterLink],
  templateUrl: './admin-dashboard.html',
  styleUrls: ['./admin-dashboard.scss']
})
export class AdminDashboardComponent implements OnInit {
  private readonly adminSvc = inject(AdminService);

  readonly loading = signal(true);
  readonly error = signal(false);
  readonly data = signal<AdminDashboard | null>(null);

  ngOnInit(): void { this.load(); }

  load(): void {
    this.loading.set(true);
    this.error.set(false);
    this.adminSvc.getDashboard().subscribe({
      next: d => { this.data.set(d); this.loading.set(false); },
      error: () => { this.error.set(true); this.loading.set(false); },
    });
  }

  methodLabel(type: string): string {
    return ({ SOURCE_BASED: 'Text & source', PHOTO_CARD: 'Photo card', MULTIMODAL: 'Text & image' } as Record<string, string>)[type] ?? type;
  }

  statusLabel(status: string): string {
    return ({
      PENDING: 'Queued', PROCESSING: 'Processing', EXPERT_REVIEW: 'In expert review',
      ESCALATED: 'Escalated — admin decision needed', FINALIZED: 'Final decision', FAILED: 'Failed',
    } as Record<string, string>)[status] ?? status;
  }

  verdictLabel(v: string | null | undefined): string {
    return v ? OVERALL_LABELS[v as OverallVerdict] ?? v : '—';
  }

  headline(c: { headline: string | null }): string {
    return c.headline || 'Headline not available yet';
  }

  /** Where a claim row leads: the admin review page for open/escalated claims, the result otherwise. */
  claimLink(c: DashboardClaim): string[] {
    return c.status === 'ESCALATED' || c.status === 'EXPERT_REVIEW' ? ['/admin/review-queue', c.submission_id] : ['/verify', c.submission_id];
  }
}
