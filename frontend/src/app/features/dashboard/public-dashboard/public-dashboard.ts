import { Component, OnInit, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { FormBuilder, ReactiveFormsModule } from '@angular/forms';
import { DashboardService } from '../../../services/dashboard.service';
import { PublicStats, TopSource, ExplorerItem } from '../../../models/admin.model';
import { ScoreBarComponent } from '../../../shared/components/score-bar/score-bar.component';
import { VerdictBadgeComponent } from '../../../shared/components/verdict-badge/verdict-badge.component';

@Component({
  selector: 'app-public-dashboard',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, RouterLink, ScoreBarComponent, VerdictBadgeComponent],
  templateUrl: './public-dashboard.html',
  styleUrls: ['./public-dashboard.scss']
})
export class PublicDashboardComponent implements OnInit {
  private readonly dashboardSvc = inject(DashboardService);
  private readonly fb = inject(FormBuilder);

  readonly loading = signal(true);
  readonly stats = signal<PublicStats | null>(null);
  readonly topSources = signal<TopSource[]>([]);

  readonly explorerLoading = signal(false);
  readonly explorerItems = signal<ExplorerItem[]>([]);
  readonly explorerTotal = signal(0);
  readonly offset = signal(0);
  readonly limit = 10;
  readonly page = () => Math.floor(this.offset() / this.limit) + 1;
  readonly pageCount = () => Math.max(1, Math.ceil(this.explorerTotal() / this.limit));

  filterForm = this.fb.group({
    keyword: [''],
    verdict: [''],
    method: [''],
    date_from: [''],
    date_to: [''],
  });

  ratio = (count: number) => {
    const total = this.stats()!.total_submissions - this.stats()!.pending_count;
    return total > 0 ? count / total : 0;
  };

  methodRatio = (count: number) => {
    const total = this.stats()!.total_submissions;
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
    this.search();
  }

  search(): void {
    this.offset.set(0);
    this.runSearch();
  }

  private runSearch(): void {
    this.explorerLoading.set(true);
    const v = this.filterForm.value;
    this.dashboardSvc.searchExplorer({
      keyword: v.keyword || undefined,
      verdict: v.verdict || undefined,
      method: v.method || undefined,
      date_from: v.date_from || undefined,
      date_to: v.date_to || undefined,
      limit: this.limit,
      offset: this.offset(),
    }).subscribe({
      next: res => {
        this.explorerItems.set(res.items);
        this.explorerTotal.set(res.total);
        this.explorerLoading.set(false);
      },
      error: () => this.explorerLoading.set(false),
    });
  }

  resetFilters(): void {
    this.filterForm.reset({ keyword: '', verdict: '', method: '', date_from: '', date_to: '' });
    this.search();
  }

  prev(): void { this.offset.update(o => Math.max(0, o - this.limit)); this.runSearch(); }
  next(): void { this.offset.update(o => o + this.limit); this.runSearch(); }

  methodLabel(m: string): string {
    switch (m) {
      case 'SOURCE_BASED': return 'Source-Based';
      case 'MULTIMODAL': return 'Multimodal';
      case 'PHOTO_CARD': return 'Photo Card';
      default: return m;
    }
  }
}
