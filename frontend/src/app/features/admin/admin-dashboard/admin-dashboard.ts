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

  // Source and content are independent checks, so each pair gets its own
  // total rather than sharing one 4-way denominator.
  get sourceTotal() { const bd = this.stats()?.verdict_breakdown; return bd ? bd.source_confirmed_count + bd.source_not_found_count : 1; }
  get contentTotal() { const bd = this.stats()?.verdict_breakdown; return bd ? bd.content_matched_count + bd.content_altered_count : 1; }
  sourceConfirmedRatio = () => (this.stats()?.verdict_breakdown.source_confirmed_count ?? 0) / this.sourceTotal;
  sourceNotFoundRatio = () => (this.stats()?.verdict_breakdown.source_not_found_count ?? 0) / this.sourceTotal;
  contentMatchedRatio = () => (this.stats()?.verdict_breakdown.content_matched_count ?? 0) / this.contentTotal;
  contentAlteredRatio = () => (this.stats()?.verdict_breakdown.content_altered_count ?? 0) / this.contentTotal;

  ngOnInit(): void {
    this.adminSvc.getStats().subscribe({
      next: s => { this.stats.set(s); this.loading.set(false); },
      error: () => this.loading.set(false),
    });
  }
}
