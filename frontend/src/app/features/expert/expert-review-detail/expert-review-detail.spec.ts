import { TestBed } from '@angular/core/testing';
import { ActivatedRoute, provideRouter } from '@angular/router';
import { of, throwError } from 'rxjs';
import { ExpertReviewDetailComponent } from './expert-review-detail';
import { ExpertService } from '../../../services/expert.service';
import { VerificationService } from '../../../services/verification.service';
import { PhotoCardService } from '../../../services/photocard.service';
import { AuthService } from '../../../services/auth.service';
import { ToastService } from '../../../shared/services/toast.service';
import { ExpertQueueItem } from '../../../models/expert.model';

const CLAIM: ExpertQueueItem = { submission_id: 's1', submission_type: 'MULTIMODAL', headline: 'বাংলা খবর', body_text: 'মূল খবরের লেখা', claimed_source_text: '', submitted_at: '2026-10-02T00:00:00Z', has_voted: false, vote_count: 1, ai_overall_verdict: 'REAL' };

describe('Reviewer workspace', () => {
  let service: jasmine.SpyObj<ExpertService>;
  function setup(claim = CLAIM, admin = false, fail = false) {
    service = jasmine.createSpyObj('ExpertService', ['getQueueItem', 'submitVote']);
    service.getQueueItem.and.returnValue(fail ? throwError(() => ({ status: 503 })) : of(claim));
    service.submitVote.and.returnValue(of({} as any));
    TestBed.configureTestingModule({ imports: [ExpertReviewDetailComponent], providers: [
      provideRouter([]), { provide: ActivatedRoute, useValue: { snapshot: { paramMap: { get: () => 's1' } } } },
      { provide: ExpertService, useValue: service },
      { provide: VerificationService, useValue: { getResult: () => throwError(() => ({ status: 503 })) } },
      { provide: PhotoCardService, useValue: { getResult: () => of({}) } },
      { provide: AuthService, useValue: { isAdmin: () => admin } },
      { provide: ToastService, useValue: { success: () => {}, error: () => {} } }
    ] });
    const fixture = TestBed.createComponent(ExpertReviewDetailComponent); fixture.detectChanges();
    return fixture;
  }
  it('keeps the text-image estimate preliminary and submits only applicable fields', () => {
    const fixture = setup(); const c = fixture.componentInstance;
    expect(fixture.nativeElement.textContent).toContain('Likely real');
    expect(fixture.nativeElement.textContent).not.toContain('Was the report found');
    c.selectOverall('MISLEADING'); c.form.setValue({ justification: 'The available evidence needs context and does not support the complete claim.' }); c.onSubmit();
    expect(service.submitVote).toHaveBeenCalledWith('s1', jasmine.objectContaining({ overall_verdict: 'MISLEADING', source_status: null, content_status: null, date_status: null }));
    fixture.detectChanges(); expect(fixture.nativeElement.textContent).toContain('Assessment recorded');
  });
  it('preserves administrator view-only access', () => {
    const fixture = setup(CLAIM, true);
    expect(fixture.nativeElement.querySelector('form')).toBeNull();
    fixture.componentInstance.onSubmit(); expect(service.submitVote).not.toHaveBeenCalled();
  });
  it('does not offer a second assessment when one is already recorded', () => {
    const fixture = setup({ ...CLAIM, has_voted: true });
    expect(fixture.nativeElement.querySelector('form')).toBeNull();
    expect(fixture.nativeElement.textContent).toContain('Assessment recorded');
  });
  it('offers recovery for a load failure instead of an empty page', () => {
    const fixture = setup(CLAIM, false, true);
    expect(fixture.nativeElement.textContent).toContain('Review temporarily unavailable');
    service.getQueueItem.and.returnValue(of(CLAIM));
    fixture.componentInstance.loadReview(); fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('মূল খবরের লেখা');
  });
  it('retains reasoning on a vote failure and does not equate a missing source with falsehood', () => {
    const fixture = setup({ ...CLAIM, submission_type: 'SOURCE_BASED' }); const c = fixture.componentInstance;
    expect(fixture.nativeElement.textContent).toContain('Comparison evidence could not be loaded');
    c.selectOverall('REAL'); c.selectSource('NOT_FOUND');
    expect(c.inconsistencyWarning()).toContain('does not prove the claim false');
    const reasoning = 'Independent evidence supports this claim even though the claimed outlet was not found.';
    c.form.setValue({ justification: reasoning });
    service.submitVote.and.returnValue(throwError(() => ({ status: 503 })));
    c.onSubmit(); fixture.detectChanges();
    expect(c.form.value.justification).toBe(reasoning);
    expect(c.submitted()).toBeFalse();
    expect(fixture.nativeElement.textContent).toContain('Your selections and reasoning are still here');
  });
});
