import { ComponentFixture, TestBed, fakeAsync, tick, discardPeriodicTasks } from '@angular/core/testing';
import { ActivatedRoute, provideRouter } from '@angular/router';
import { of, throwError } from 'rxjs';
import { VerifyResultComponent } from './verify-result';
import { VerificationService, MultimodalService } from '../../../services/verification.service';
import { SubmissionsService } from '../../../services/submissions.service';
import { PhotoCardService } from '../../../services/photocard.service';
import { PhotoCardResultResponse } from '../../../models/photocard.model';
import { SubmissionLookup, VerificationResponse } from '../../../models/verification.model';

const LOOKUP: SubmissionLookup = {
  submission_id: 'p1',
  submission_type: 'PHOTO_CARD',
  status: 'PROCESSING',
  headline: null,
  created_at: '2026-06-07T10:00:00Z',
};

function pendingCard(over: Partial<PhotoCardResultResponse> = {}): PhotoCardResultResponse {
  return {
    submission_id: 'p1',
    status: 'PROCESSING',
    phase: 'EXTRACTING',
    claim_scope: 'HEADLINE_ONLY',
    headline: null,
    claimed_source_text: 'প্রথম আলো',
    image_url: 'https://minio/p1.png',
    extraction_warnings: [],
    verification: null,
    created_at: '2026-06-07T10:00:00Z',
    ...over,
  };
}

const VERIFICATION: VerificationResponse = {
  submission_id: 'p1',
  source_status: 'CONFIRMED',
  content_status: 'MATCHED',
  confidence: 0.9,
  reasoning: 'ok',
  matched_articles: [],
  scores: { headline_similarity: 0.95, body_similarity: null },
  manipulation_flags: { check_states: { headline: 'PASSED', body: 'NOT_APPLICABLE' } },
  cached: false,
  created_at: '2026-06-07T10:05:00Z',
  claim_scope: 'HEADLINE_ONLY',
  review_pending: true,
  is_finalized: false,
  overall_verdict: null,
} as VerificationResponse;

describe('VerifyResultComponent (photo card, returning later)', () => {
  let photocard: jasmine.SpyObj<PhotoCardService>;
  let lookupSpy: jasmine.Spy;

  function setup(lookup: SubmissionLookup = LOOKUP): ComponentFixture<VerifyResultComponent> {
    photocard = jasmine.createSpyObj('PhotoCardService', ['getResult']);
    lookupSpy = jasmine.createSpy().and.returnValue(of(lookup));
    TestBed.configureTestingModule({
      imports: [VerifyResultComponent],
      providers: [
        provideRouter([]),
        { provide: ActivatedRoute, useValue: { snapshot: { paramMap: { get: () => 'p1' } } } },
        { provide: SubmissionsService, useValue: { getLookup: lookupSpy } },
        { provide: PhotoCardService, useValue: photocard },
        { provide: VerificationService, useValue: {} },
        { provide: MultimodalService, useValue: {} },
      ],
    });
    return TestBed.createComponent(VerifyResultComponent);
  }

  it('renders a pending photo card from its own state: image, progress, no headline needed', () => {
    const fixture = setup();
    photocard.getResult.and.returnValue(of(pendingCard()));
    fixture.detectChanges();
    const el = fixture.nativeElement as HTMLElement;
    expect(el.querySelector('img.media-image')?.getAttribute('src')).toBe('https://minio/p1.png');
    expect(el.textContent).toContain('Reading the headline from the card');
    expect(el.textContent).toContain('You can leave this page');
    expect(el.textContent).not.toContain('Awaiting expert review'); // not shown as a completed result
    fixture.destroy();
  });

  it('polls only while pending, stops once complete, and stops when the page is left', fakeAsync(() => {
    const fixture = setup();
    photocard.getResult.and.returnValue(of(pendingCard()));
    fixture.detectChanges();
    expect(photocard.getResult).toHaveBeenCalledTimes(1);

    tick(4000);
    expect(photocard.getResult).toHaveBeenCalledTimes(2); // still pending -> keeps following

    photocard.getResult.and.returnValue(of(pendingCard({ status: 'EXPERT_REVIEW', phase: 'DONE', headline: 'শিরোনাম', verification: VERIFICATION })));
    tick(4000);
    const callsWhenDone = photocard.getResult.calls.count();
    fixture.detectChanges();
    const el = fixture.nativeElement as HTMLElement;
    expect(el.textContent).toContain('Awaiting expert review');   // preliminary: no overall truth badge
    expect(el.textContent).toContain('শিরোনাম');
    expect(el.querySelector('.scores-grid')?.textContent).not.toContain('Body');

    tick(12000);
    expect(photocard.getResult.calls.count()).toBe(callsWhenDone); // completed: polling stopped

    fixture.destroy();
    discardPeriodicTasks();
  }));

  it('leaving the page stops its polling (the server job is unaffected)', fakeAsync(() => {
    const fixture = setup();
    photocard.getResult.and.returnValue(of(pendingCard()));
    fixture.detectChanges();
    tick(4000);
    const before = photocard.getResult.calls.count();
    fixture.destroy(); // navigate away
    tick(20000);
    expect(photocard.getResult.calls.count()).toBe(before);
    discardPeriodicTasks();
  }));

  it('a service failure offers retry without claiming the result was removed', () => {
    const fixture = setup();
    lookupSpy.and.returnValue(throwError(() => ({ status: 503 })));
    fixture.detectChanges();
    const el = fixture.nativeElement as HTMLElement;
    expect(el.textContent).toContain('Result temporarily unavailable');
    expect(el.textContent).not.toContain('Result not found');
    photocard.getResult.and.returnValue(of(pendingCard()));
    lookupSpy.and.returnValue(of(LOOKUP));
    fixture.componentInstance.retry();
    fixture.detectChanges();
    expect(el.textContent).toContain('Verification in progress');
    expect(el.textContent).not.toContain('Result temporarily unavailable');
    fixture.destroy();
  });

  it('a failed card shows the reason and no verdict', () => {
    const fixture = setup({ ...LOOKUP, status: 'FAILED' });
    photocard.getResult.and.returnValue(
      of(pendingCard({ status: 'FAILED', phase: 'FAILED', failure_reason: 'Could not extract a readable headline from this photo card.' })),
    );
    fixture.detectChanges();
    const el = fixture.nativeElement as HTMLElement;
    expect(el.textContent).toContain('Verification could not be completed');
    expect(el.textContent).toContain('We could not read the headline');
    expect(el.textContent).toContain('No verdict was reached');
    fixture.destroy();
  });
});
