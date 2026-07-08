import { Component, OnInit, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ExpertService } from '../../../services/expert.service';
import { ExpertStats } from '../../../models/expert.model';
import { ScoreBarComponent } from '../../../shared/components/score-bar/score-bar.component';

@Component({
  selector: 'app-expert-stats',
  standalone: true,
  imports: [CommonModule, ScoreBarComponent],
  templateUrl: './expert-stats.html',
  styleUrls: ['./expert-stats.scss']
})
export class ExpertStatsComponent implements OnInit {
  private readonly expertSvc = inject(ExpertService);

  readonly loading = signal(true);
  readonly stats = signal<ExpertStats | null>(null);

  scoreColor = () => {
    const s = this.stats()?.current_credibility ?? 0;
    if (s >= 0.7) return 'var(--success)';
    if (s >= 0.4) return 'var(--warning)';
    return 'var(--error)';
  };

  ngOnInit(): void {
    this.expertSvc.getStats().subscribe({
      next: s => { this.stats.set(s); this.loading.set(false); },
      error: () => this.loading.set(false),
    });
  }
}
