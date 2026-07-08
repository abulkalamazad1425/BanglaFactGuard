import { Component, OnInit, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { DashboardService } from '../../../services/dashboard.service';
import { PublicStats, TopSource } from '../../../models/admin.model';
import { ScoreBarComponent } from '../../../shared/components/score-bar/score-bar.component';

@Component({
  selector: 'app-public-dashboard',
  standalone: true,
  imports: [CommonModule, ScoreBarComponent],
  templateUrl: './public-dashboard.html',
  styleUrls: ['./public-dashboard.scss']
})
export class PublicDashboardComponent implements OnInit {
  private readonly dashboardSvc = inject(DashboardService);

  readonly loading = signal(true);
  readonly stats = signal<PublicStats | null>(null);
  readonly topSources = signal<TopSource[]>([]);

  ratio = (count: number) => {
    const total = this.stats()!.total_submissions - this.stats()!.pending_count;
    return total > 0 ? count / total : 0;
  };

  ngOnInit(): void {
    this.dashboardSvc.getPublicStats().subscribe({
      next: s => { this.stats.set(s); this.loading.set(false); },
      error: () => this.loading.set(false),
    });
    this.dashboardSvc.getTopSources(10).subscribe({
      next: t => this.topSources.set(t), error: () => { },
    });
  }
}
