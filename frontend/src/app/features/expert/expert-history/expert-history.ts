import { Component, OnInit, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { ExpertService } from '../../../services/expert.service';
import { ExpertHistoryItem } from '../../../models/expert.model';
import { VerdictBadgeComponent } from '../../../shared/components/verdict-badge/verdict-badge.component';

@Component({
  selector: 'app-expert-history',
  standalone: true,
  imports: [CommonModule, RouterLink, VerdictBadgeComponent],
  templateUrl: './expert-history.html',
  styleUrls: ['./expert-history.scss']
})
export class ExpertHistoryComponent implements OnInit {
  private readonly expertSvc = inject(ExpertService);

  readonly loading = signal(true);
  readonly history = signal<ExpertHistoryItem[]>([]);

  ngOnInit(): void {
    this.expertSvc.getHistory(50).subscribe({
      next: h => { this.history.set(h); this.loading.set(false); },
      error: () => this.loading.set(false),
    });
  }
}
