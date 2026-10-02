import { TestBed } from '@angular/core/testing';
import { VerificationReportComponent } from './verification-report.component';
import { VerificationResponse } from '../../../models/verification.model';

function base(overrides: Partial<VerificationResponse> = {}): VerificationResponse {
  return {
    submission_id: 's1',
    source_status: 'CONFIRMED',
    content_status: 'MATCHED',
    date_status: null,
    ai_source_status: 'CONFIRMED',
    ai_content_status: 'MATCHED',
    confidence: 0.9,
    reasoning: 'A corresponding report was found.',
    matched_articles: [],
    scores: { headline_similarity: 0.95, body_similarity: 0.1, headline_keyword_coverage: 1 },
    manipulation_flags: { check_states: { headline: 'PASSED', body: 'PASSED', numbers: 'NOT_EVALUATED' } },
    cached: false,
    created_at: '2026-06-07T10:00:00Z',
    claim_scope: 'HEADLINE_ONLY',
    is_finalized: false,
    review_pending: true,
    overall_verdict: null,
    ...overrides,
  } as VerificationResponse;
}

function render(r: VerificationResponse): HTMLElement {
  const fixture = TestBed.createComponent(VerificationReportComponent);
  fixture.componentRef.setInput('r', r);
  fixture.detectChanges();
  return fixture.nativeElement as HTMLElement;
}

describe('VerificationReportComponent', () => {
  beforeEach(() => TestBed.configureTestingModule({ imports: [VerificationReportComponent] }));

  it('before finalization shows review-pending and NO overall truth badge', () => {
    const el = render(base());
    expect(el.textContent).toContain('Awaiting expert review');
    expect(el.textContent).not.toContain('Expert verified');
    const badgeTexts = Array.from(el.querySelectorAll('.badge')).map((b) =>
      (b.textContent ?? '').replace(/[^A-Za-z]/g, ''),
    );
    expect(badgeTexts.some((t) => ['Fake', 'Real', 'Misleading', 'Altered'].includes(t))).toBeFalse();
  });

  it('after finalization shows the expert verdict, and the automated result stays inspectable', () => {
    const el = render(
      base({ is_finalized: true, review_pending: false, overall_verdict: 'MISLEADING', was_overridden: true, content_status: 'ALTERED' }),
    );
    expect(el.textContent).toContain('Expert verified');
    expect(el.textContent).toContain('Misleading');
    expect(el.textContent).toContain('Experts changed the automated finding');
  });

  it('photo card (headline-only): no Body Match score and no body check, even if a stale value arrives', () => {
    const el = render(base());
    expect(el.textContent).not.toContain('Submitted body');
    expect(el.textContent).not.toContain('Body Match');
    expect(el.textContent).toContain('Headline only');
  });

  it('text with body shows body comparison', () => {
    const el = render(base({ claim_scope: 'HEADLINE_WITH_BODY', scores: { headline_similarity: 0.9, body_similarity: 0.8 } }));
    expect(el.textContent).toContain('Submitted body vs source body');
  });

  it('green ticks are only for completed passes; unevaluated checks are neutral', () => {
    const el = render(base());
    const cards = Array.from(el.querySelectorAll('.check-card'));
    const passed = cards.filter((c) => c.classList.contains('passed'));
    const unknown = cards.filter((c) => c.classList.contains('unknown'));
    expect(passed.length).toBe(1); // headline only (body hidden for headline-only)
    expect(unknown.length).toBe(1); // numbers not evaluated
    expect(unknown[0].textContent).toContain('Not evaluated');
  });

  it('Content Altered lists the supporting discrepancy with both texts', () => {
    const el = render(
      base({
        content_status: 'ALTERED',
        ai_content_status: 'ALTERED',
        manipulation_flags: {
          check_states: { numbers: 'FAILED' },
          discrepancies: [
            { kind: 'numbers', claim_text: 'ক ৫ জন', evidence_text: 'ক ১০ জন', detail: 'claimed 5, source states 10', part: 'headline' },
          ],
        },
      }),
    );
    expect(el.textContent).toContain('claimed 5, source states 10');
    expect(el.textContent).toContain('ক ৫ জন');
    expect(el.textContent).toContain('ক ১০ জন');
  });

  it('source not confirmed hides content scores and shows search coverage, with no strength figure', () => {
    const el = render(
      base({
        source_status: 'INCOMPLETE',
        content_status: null,
        confidence: 0,
        analysis: {
          metrics: {}, passages: [], source_basis: ['search incomplete'], content_basis: [],
          search: { attempted: 5, success: 0, success_empty: 0, failed: 5, skipped: 0, cached: 0, adequate: false },
        },
      }),
    );
    expect(el.textContent).toContain('Search coverage');
    expect(el.textContent).toContain('5 failed');
    expect(el.querySelector('.scores-grid')).toBeNull();
    expect(el.querySelector('.confidence-val')!.textContent!.trim()).toBe('—');
  });

  it('labels the strength meter as a measurement, not a probability', () => {
    const el = render(base());
    expect(el.querySelector('.confidence-lbl')!.textContent).toContain('Check strength');
    expect(el.querySelector('.confidence-meter')!.getAttribute('title')).toContain('not the probability');
  });

  it('retrieval relevance is labelled as such and distinct from content match', () => {
    const el = render(
      base({ matched_articles: [{ url: 'https://prothomalo.com/a/b', title: 'T', rank_score: 0.8 } as any] }),
    );
    expect(el.textContent).toContain('Retrieval relevance: 80%');
    expect(el.textContent).toContain('Content match against the claimed source');
  });
});
