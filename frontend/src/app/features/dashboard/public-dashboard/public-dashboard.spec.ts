import { TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';
import { of, Subject, throwError } from 'rxjs';
import { PublicDashboardComponent } from './public-dashboard';
import { DashboardService } from '../../../services/dashboard.service';
import { SourceService } from '../../../services/source.service';
import { ExplorerItem, ExplorerSearchResponse } from '../../../models/admin.model';

const REVIEW: ExplorerItem = { submission_id: 'claim-1', headline: 'বাংলা সংবাদ যাচাই', submission_type: 'PHOTO_CARD', claimed_source_text: 'News outlet', overall_verdict: null, is_finalized: false, source_status: 'NOT_FOUND', content_status: null, date_status: null, confidence: null, published_date: null, created_at: '2026-10-02T10:00:00Z' };
const response = (items: ExplorerItem[] = [], total = items.length): ExplorerSearchResponse => ({ items, total, limit: 10, offset: 0, archive_summary: { total: 23, finalized: 3, review: 20 } });

describe('Fact Explorer archive', () => {
  let service: jasmine.SpyObj<DashboardService>;
  beforeEach(() => {
    service = jasmine.createSpyObj('DashboardService', ['searchExplorer']);
    service.searchExplorer.and.returnValue(of(response()));
    TestBed.configureTestingModule({
      providers: [provideRouter([{ path: 'dashboard', component: PublicDashboardComponent }]),
        { provide: DashboardService, useValue: service },
        { provide: SourceService, useValue: { listSources: () => of({ items: [] }) } }]
    });
  });

  it('defaults to final decisions and uses archive counts, even with an empty page', async () => {
    const harness = await RouterTestingHarness.create('/dashboard');
    expect(service.searchExplorer).toHaveBeenCalledWith(jasmine.objectContaining({ review_state: 'finalized', offset: 0 }));
    const text = harness.routeNativeElement!.textContent!;
    expect(text).toContain('No final decisions yet');
    expect(text).toContain('23');
    expect(text).not.toContain('Average Verification Time');
  });

  it('does not turn a missing source into a fake verdict', async () => {
    service.searchExplorer.and.returnValue(of(response([REVIEW])));
    const harness = await RouterTestingHarness.create('/dashboard?review=review');
    expect(harness.routeNativeElement!.textContent).toContain('does not establish that the claim is false');
    expect(harness.routeNativeElement!.querySelector('.badge-false')).toBeNull();
    expect(harness.routeNativeElement!.textContent).toContain('Under expert review');
  });

  it('restores search and page from a shared URL', async () => {
    service.searchExplorer.and.returnValue(of(response([REVIEW], 20)));
    await RouterTestingHarness.create('/dashboard?review=review&keyword=news&method=PHOTO_CARD&page=2');
    expect(service.searchExplorer).toHaveBeenCalledWith(jasmine.objectContaining({ keyword: 'news', method: 'PHOTO_CARD', review_state: 'review', offset: 10 }));
  });

  it('rejects reversed date ranges without sending a search', async () => {
    const harness = await RouterTestingHarness.create();
    const component = await harness.navigateByUrl('/dashboard', PublicDashboardComponent);
    service.searchExplorer.calls.reset();
    component.filterForm.patchValue({ date_from: '2026-10-03', date_to: '2026-10-02' });
    component.search();
    expect(component.validation()).toContain('end date');
    expect(service.searchExplorer).not.toHaveBeenCalled();
  });

  it('keeps service failure distinct from no results and supports retry', async () => {
    service.searchExplorer.and.returnValue(throwError(() => ({ status: 503 })));
    const harness = await RouterTestingHarness.create();
    const component = await harness.navigateByUrl('/dashboard', PublicDashboardComponent);
    expect(harness.routeNativeElement!.textContent).toContain('couldn’t load the archive');
    expect(harness.routeNativeElement!.textContent).not.toContain('No final decisions yet');
    service.searchExplorer.and.returnValue(of(response()));
    component.retry(); harness.detectChanges();
    expect(component.error()).toBeFalse();
    expect(harness.routeNativeElement!.textContent).toContain('No final decisions yet');
  });

  it('cancels a stale request when the user changes the archive view', async () => {
    const stale = new Subject<ExplorerSearchResponse>();
    service.searchExplorer.and.returnValue(stale);
    const harness = await RouterTestingHarness.create();
    const component = await harness.navigateByUrl('/dashboard', PublicDashboardComponent);
    service.searchExplorer.and.returnValue(of(response([REVIEW])));
    await TestBed.inject(Router).navigateByUrl('/dashboard?review=review');
    stale.next(response([], 90));
    expect(component.total()).toBe(1);
    expect(component.items()[0].submission_id).toBe('claim-1');
  });
});
