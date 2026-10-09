import { TestBed, fakeAsync, tick } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { of } from 'rxjs';
import { SubmissionHistoryComponent } from './submission-history';
import { VerificationService } from '../../../services/verification.service';

describe('My Submissions search and filters', () => {
  function setup() {
    const svc = {
      getMySubmissions: jasmine.createSpy('getMySubmissions').and.returnValue(of([])),
      getMyStats: () => of(null),
    };
    TestBed.configureTestingModule({
      imports: [SubmissionHistoryComponent],
      providers: [provideRouter([]), { provide: VerificationService, useValue: svc }],
    });
    const fixture = TestBed.createComponent(SubmissionHistoryComponent);
    fixture.detectChanges();
    return { fixture, cmp: fixture.componentInstance, svc };
  }

  const lastFilters = (svc: { getMySubmissions: jasmine.Spy }) =>
    svc.getMySubmissions.calls.mostRecent().args;

  it('sends search, status and type to the server and restarts at page 1', fakeAsync(() => {
    const { cmp, svc } = setup();
    cmp.goToPage(3);
    cmp.onSearchInput('  মেট্রোরেল ');
    tick(300);
    expect(lastFilters(svc)).toEqual([11, 0, { q: 'মেট্রোরেল', state: '', type: '' }]);

    cmp.setState('final');
    cmp.setType('PHOTO_CARD');
    expect(lastFilters(svc)).toEqual([
      11,
      0,
      { q: 'মেট্রোরেল', state: 'final', type: 'PHOTO_CARD' },
    ]);
    expect(cmp.filtered()).toBeTrue();
  }));

  it('offers to clear the search when nothing matches', () => {
    const { fixture, cmp, svc } = setup();
    cmp.setState('failed');
    fixture.detectChanges();
    const el = fixture.nativeElement as HTMLElement;
    expect(el.textContent).toContain('No submissions match');

    (el.querySelector('.empty-state button') as HTMLButtonElement).click();
    fixture.detectChanges();
    expect(lastFilters(svc)).toEqual([11, 0, { q: '', state: '', type: '' }]);
    expect(cmp.filtered()).toBeFalse();
    expect(el.textContent).toContain('No submissions on this page');
  });
});
