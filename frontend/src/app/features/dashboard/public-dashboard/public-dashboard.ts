import { Component, DestroyRef, OnInit, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { FormBuilder, ReactiveFormsModule } from '@angular/forms';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { Subscription } from 'rxjs';
import { DashboardService } from '../../../services/dashboard.service';
import { SourceService } from '../../../services/source.service';
import { ExplorerItem, ExplorerSearchParams, ExplorerSearchResponse } from '../../../models/admin.model';
import { SourceResponse } from '../../../models/source.model';
import { VerdictBadgeComponent } from '../../../shared/components/verdict-badge/verdict-badge.component';

const EMPTY = { keyword: '', overall_verdict: '', method: '', source_id: '', date_from: '', date_to: '' };
type FilterKey = keyof typeof EMPTY;

@Component({
  selector: 'app-public-dashboard', standalone: true,
  imports: [CommonModule, ReactiveFormsModule, RouterLink, VerdictBadgeComponent],
  templateUrl: './public-dashboard.html', styleUrls: ['./public-dashboard.scss']
})
export class PublicDashboardComponent implements OnInit {
  private readonly dashboardSvc = inject(DashboardService);
  private readonly sourceSvc = inject(SourceService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly destroyRef = inject(DestroyRef);
  private request?: Subscription;
  readonly filterForm = inject(FormBuilder).nonNullable.group(EMPTY);
  readonly loading = signal(true);
  readonly error = signal(false);
  readonly validation = signal('');
  readonly items = signal<ExplorerItem[]>([]);
  readonly total = signal(0);
  readonly summary = signal<ExplorerSearchResponse['archive_summary']>(undefined);
  readonly reviewState = signal<'finalized' | 'review'>('finalized');
  readonly advanced = signal(false);
  readonly sources = signal<SourceResponse[]>([]);
  readonly sourcesError = signal(false);
  readonly failedImages = signal(new Set<string>());
  readonly activeFilters = signal<{ key: FilterKey; label: string }[]>([]);
  readonly page = signal(1);
  readonly limit = 10;
  readonly pageCount = () => Math.max(1, Math.ceil(this.total() / this.limit));
  readonly first = () => (this.page() - 1) * this.limit + 1;
  readonly last = () => Math.min(this.page() * this.limit, this.total());

  ngOnInit(): void {
    this.loadSources();
    this.route.queryParamMap.pipe(takeUntilDestroyed(this.destroyRef)).subscribe(params => {
      const state = params.get('review') === 'review' ? 'review' : 'finalized';
      this.reviewState.set(state);
      const values = { ...EMPTY };
      for (const key of Object.keys(values) as FilterKey[]) values[key] = params.get(key) || '';
      if (!['REAL', 'FAKE', 'MISLEADING', 'ALTERED'].includes(values.overall_verdict) || state === 'review') values.overall_verdict = '';
      if (!['SOURCE_BASED', 'PHOTO_CARD', 'MULTIMODAL'].includes(values.method)) values.method = '';
      this.filterForm.reset(values);
      this.page.set(Math.min(100000, Math.max(1, Math.floor(Number(params.get('page')) || 1))));
      if (values.source_id || values.date_from || values.date_to) this.advanced.set(true);
      this.runSearch();
    });
    this.destroyRef.onDestroy(() => this.request?.unsubscribe());
  }

  loadSources(): void {
    this.sourcesError.set(false);
    this.sourceSvc.listSources(undefined, 1, 100).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: response => { this.sources.set(response.items); this.updateChips(); },
      error: () => this.sourcesError.set(true)
    });
  }

  private valid(): boolean {
    const { date_from, date_to } = this.filterForm.getRawValue();
    const validDate = (value: string) => !value || (/^\d{4}-\d{2}-\d{2}$/.test(value) && !Number.isNaN(Date.parse(value)));
    this.validation.set(!validDate(date_from) || !validDate(date_to) ? 'Enter a valid date.' : date_from && date_to && date_from > date_to ? 'The end date must be on or after the start date.' : '');
    return !this.validation();
  }

  search(): void { if (this.valid()) this.navigate(1); }
  resetFilters(): void { this.filterForm.reset(EMPTY); this.navigate(1); }
  removeFilter(key: FilterKey): void { this.filterForm.controls[key].setValue(''); this.search(); }
  selectState(state: 'finalized' | 'review'): void {
    this.reviewState.set(state);
    this.filterForm.controls.overall_verdict.setValue('');
    this.navigate(1);
  }
  changePage(page: number): void { if (page >= 1 && page <= this.pageCount()) this.navigate(page); }
  private navigate(page: number): void {
    const values = this.filterForm.getRawValue();
    values.keyword = values.keyword.trim();
    const queryParams: Record<string, string | number | null> = { review: this.reviewState(), page: page > 1 ? page : null };
    for (const key of Object.keys(values) as FilterKey[]) queryParams[key] = values[key] || null;
    this.router.navigate([], { relativeTo: this.route, queryParams }).then(changed => {
      if (!changed) { this.page.set(page); this.runSearch(); }
    });
  }

  retry(): void { this.runSearch(); }
  private runSearch(): void {
    this.request?.unsubscribe();
    if (!this.valid()) { this.loading.set(false); this.items.set([]); return; }
    this.loading.set(true); this.error.set(false); this.updateChips();
    const values = this.filterForm.getRawValue();
    const params: ExplorerSearchParams = { review_state: this.reviewState(), limit: this.limit, offset: (this.page() - 1) * this.limit };
    for (const key of Object.keys(values) as FilterKey[]) if (values[key]) params[key] = values[key];
    this.request = this.dashboardSvc.searchExplorer(params).subscribe({
      next: response => {
        this.summary.set(response.archive_summary);
        this.total.set(response.total);
        if (this.page() > this.pageCount()) { this.navigate(this.pageCount()); return; }
        this.items.set(response.items); this.loading.set(false);
      },
      error: () => { this.error.set(true); this.loading.set(false); }
    });
  }

  private updateChips(): void {
    const values = this.filterForm.getRawValue();
    const labels: Record<FilterKey, string> = {
      keyword: `Search: ${values.keyword}`, overall_verdict: `Decision: ${this.verdictLabel(values.overall_verdict)}`,
      method: this.methodLabel(values.method), source_id: `Claimed outlet: ${this.sources().find(s => s.id === values.source_id)?.display_name || 'Selected outlet'}`,
      date_from: `Submitted from: ${values.date_from}`, date_to: `Submitted through: ${values.date_to}`
    };
    this.activeFilters.set((Object.keys(values) as FilterKey[]).filter(key => !!values[key]).map(key => ({ key, label: labels[key] })));
  }
  imageFailed(id: string): void { this.failedImages.update(ids => new Set([...ids, id])); }
  methodLabel(method: string): string { return ({ SOURCE_BASED: 'News text', PHOTO_CARD: 'Photocard', MULTIMODAL: 'Text and image' } as Record<string, string>)[method] || 'News check'; }
  verdictLabel(verdict: string): string { return ({ REAL: 'Real', FAKE: 'Fake', MISLEADING: 'Misleading', ALTERED: 'Altered' } as Record<string, string>)[verdict] || ''; }
  finding(item: ExplorerItem): string {
    if (item.submission_type === 'MULTIMODAL') return item.is_finalized
      ? 'Expert review is complete. Read the full report for the assessment and its limitations.'
      : 'A preliminary assessment is available. Expert review is needed before a final decision.';
    let text = item.source_status === 'CONFIRMED' ? 'A related report was found on the claimed news outlet.'
      : item.source_status === 'NOT_FOUND' ? 'No matching report was found in the available source search. This does not establish that the claim is false.'
      : 'The source check is incomplete. The available findings do not establish whether the claim is true or false.';
    if (item.source_status === 'CONFIRMED') {
      if (item.content_status === 'MATCHED') text += ' The checked content matches.';
      else if (item.content_status === 'ALTERED') text += ' Differences were found in the checked content.';
      else text += ' The content check is incomplete.';
    }
    if (item.date_status === 'MISMATCHED') text += ' The claimed date does not match the source.';
    return text;
  }
}
