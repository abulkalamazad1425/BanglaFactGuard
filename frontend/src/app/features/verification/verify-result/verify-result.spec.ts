import { signal } from '@angular/core';
import { AuthService } from '../../../services/auth.service';
import {
  ComponentFixture,
  TestBed,
  fakeAsync,
  tick,
  discardPeriodicTasks,
} from '@angular/core/testing';
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
    claimed_source_text: null,
    image_url: 'https://minio/p1.png',
    extraction_status: 'PENDING',
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
  headline_check_status: 'COMPLETED',
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
        { provide: AuthService, useValue: { isLoggedIn: signal(false) } },
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
    expect(el.textContent).toContain('Reading the headline, outlet and date from the card');
    expect(el.textContent).toContain('You can leave this page');
    expect(el.textContent).not.toContain('Expert review pending.'); // not shown as a completed result
    fixture.destroy();
  });

  it('polls only while pending, stops once complete, and stops when the page is left', fakeAsync(() => {
    const fixture = setup();
    photocard.getResult.and.returnValue(of(pendingCard()));
    fixture.detectChanges();
    expect(photocard.getResult).toHaveBeenCalledTimes(1);

    tick(4000);
    expect(photocard.getResult).toHaveBeenCalledTimes(2); // still pending -> keeps following

    photocard.getResult.and.returnValue(
      of(
        pendingCard({
          status: 'EXPERT_REVIEW',
          phase: 'DONE',
          headline: 'শিরোনাম',
          verification: VERIFICATION,
        }),
      ),
    );
    tick(4000);
    const callsWhenDone = photocard.getResult.calls.count();
    fixture.detectChanges();
    const el = fixture.nativeElement as HTMLElement;
    expect(el.textContent).toContain('Expert review pending.'); // preliminary: no overall truth badge
    expect(el.textContent).toContain('শিরোনাম');
    expect(el.textContent).not.toContain('BODY SIMILARITY'); // a photo card has no body scores

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
      of(
        pendingCard({
          status: 'FAILED',
          phase: 'FAILED',
          failure_reason: 'Could not extract a readable headline from this photo card.',
        }),
      ),
    );
    fixture.detectChanges();
    const el = fixture.nativeElement as HTMLElement;
    expect(el.textContent).toContain('Verification could not be completed');
    expect(el.textContent).toContain('We could not read the headline');
    expect(el.textContent).toContain('No verdict was reached');
    fixture.destroy();
  });
});

describe('VerifyResultComponent (photo card extraction preview)', () => {
  function render(card: PhotoCardResultResponse): HTMLElement {
    TestBed.configureTestingModule({
      imports: [VerifyResultComponent],
      providers: [
        provideRouter([]),
        { provide: AuthService, useValue: { isLoggedIn: signal(false) } },
        { provide: ActivatedRoute, useValue: { snapshot: { paramMap: { get: () => 'p1' } } } },
        {
          provide: SubmissionsService,
          useValue: { getLookup: () => of({ ...LOOKUP, status: 'EXPERT_REVIEW' }) },
        },
        { provide: PhotoCardService, useValue: { getResult: () => of(card) } },
        { provide: VerificationService, useValue: {} },
        { provide: MultimodalService, useValue: {} },
      ],
    });
    const fixture = TestBed.createComponent(VerifyResultComponent);
    fixture.detectChanges();
    return fixture.nativeElement as HTMLElement;
  }

  it('shows the outlet and date read from the card once, as the claimed values', () => {
    const el = render(
      pendingCard({
        status: 'EXPERT_REVIEW',
        phase: 'DONE',
        headline: 'শিরোনাম',
        verification: VERIFICATION,
        extraction_status: 'SUCCEEDED',
        extraction_attempts: 2,
        claimed_source_text: 'prothomalo.com',
        claimed_source_name: 'প্রথম আলো',
        published_date: '2026-10-05',
      }),
    );
    const text = el.textContent ?? '';
    expect(text).toContain('Claimed news outlet');
    expect(text).toContain('প্রথম আলো');
    expect(text).toContain('5 Oct 2026');
    expect(text).toContain('succeeded on attempt 2 of 9');
    // one representation: no separate "shown on the card" or "selected" values
    expect(text).not.toContain('Outlet shown on the card');
    expect(text).not.toContain('Date shown on the card');
    expect(text).not.toContain('Selected outlet');
    expect(text).not.toContain('OCR');
  });

  it('a card without a printed date says so instead of inventing one', () => {
    const el = render(
      pendingCard({
        status: 'EXPERT_REVIEW',
        phase: 'DONE',
        headline: 'শিরোনাম',
        verification: VERIFICATION,
        extraction_status: 'SUCCEEDED',
        claimed_source_text: 'prothomalo.com',
        claimed_source_name: 'প্রথম আলো',
        published_date: null,
      }),
    );
    expect(el.textContent).toContain('Not shown on the card');
  });

  it('distinguishes an unreadable card from one without a headline or recognised outlet', () => {
    const apiFailed = render(
      pendingCard({
        status: 'FAILED',
        phase: 'FAILED',
        extraction_status: 'API_FAILED',
        failure_reason:
          'Sorry for the temporary inconvenience. Information cannot be collected from the photo card right now. Please submit it again after a while.',
      }),
    );
    expect(apiFailed.textContent).toContain('Please submit it again after a while');
    expect(apiFailed.textContent).toContain('The card could not be read.');
    TestBed.resetTestingModule();
    const invalid = render(
      pendingCard({
        status: 'FAILED',
        phase: 'FAILED',
        extraction_status: 'INVALID_CONTENT',
        failure_reason:
          "A valid headline or a recognized news outlet could not be identified on the photo card. Please submit a photo card with a clear headline and the news outlet's name or logo.",
      }),
    );
    expect(invalid.textContent).toContain(
      'No valid headline or recognised news outlet was found on this card.',
    );
    expect(invalid.textContent).toContain('clear headline');
  });
});
