import { Component, OnInit, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { AdminService } from '../../../services/admin.service';
import { AdminStats, ExpertResponse } from '../../../models/admin.model';
import { ScoreBarComponent } from '../../../shared/components/score-bar/score-bar.component';

@Component({
  selector: 'app-admin-dashboard',
  standalone: true,
  imports: [CommonModule, RouterLink, ScoreBarComponent],
  templateUrl: './admin-dashboard.html',
  styleUrls: ['./admin-dashboard.scss']
})
export class AdminDashboardComponent implements OnInit {
  private readonly adminSvc = inject(AdminService);

  readonly loading = signal(true);
  readonly stats = signal<AdminStats | null>(null);

  get total() { const bd = this.stats()?.verdict_breakdown; return bd ? bd.true_count + bd.false_count + bd.partially_true_count + bd.not_found_count : 1; }
  trueRatio = () => (this.stats()?.verdict_breakdown.true_count ?? 0) / this.total;
  falseRatio = () => (this.stats()?.verdict_breakdown.false_count ?? 0) / this.total;
  partialRatio = () => (this.stats()?.verdict_breakdown.partially_true_count ?? 0) / this.total;
  nfRatio = () => (this.stats()?.verdict_breakdown.not_found_count ?? 0) / this.total;

  ngOnInit(): void {
    this.adminSvc.getStats().subscribe({
      next: s => { this.stats.set(s); this.loading.set(false); },
      error: () => this.loading.set(false),
    });
  }
}
