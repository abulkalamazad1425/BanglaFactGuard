import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { VerificationReportComponent } from './verification-report.component';
import { HeadlineAlterationDetail, VerificationResponse } from '../../../models/verification.model';

const MATCHED_DETAIL: HeadlineAlterationDetail = {
  status: 'COMPLETED',
  verdict: 'MATCHED',
  reason: 'The claim headline exactly matches the source title.',
  exact_match: true,
  claim_headline: 'নতুন সেতুর উদ্বোধন',
  source_title: 'নতুন সেতুর উদ্বোধন',
  source_publisher: 'prothomalo.com',
  source_url: 'https://prothomalo.com/a/b',
  differences: [],
};

function base(overrides: Partial<VerificationResponse> = {}): VerificationResponse {
  return {
    submission_id: 's1',
    source_status: 'CONFIRMED',
    content_status: 'MATCHED',
    headline_check_status: 'COMPLETED',
    date_status: null,
    ai_source_status: 'CONFIRMED',
    ai_content_status: 'MATCHED',
    confidence: 0.9,
    reasoning: 'A corresponding report was found.',
    matched_articles: [],
    cached: false,
    created_at: '2026-06-07T10:00:00Z',
    claim_scope: 'HEADLINE_ONLY',
    is_finalized: false,
    review_pending: true,
    overall_verdict: null,
    analysis: { headline_alteration: MATCHED_DETAIL, body_similarity: { status: 'SKIPPED' } },
    ...overrides,
  } as VerificationResponse;
}

function render(r: VerificationResponse, reviewer = false): HTMLElement {
  const fixture = TestBed.createComponent(VerificationReportComponent);
  fixture.componentRef.setInput('r', r);
  fixture.componentRef.setInput('reviewer', reviewer);
  fixture.detectChanges();
  return fixture.nativeElement as HTMLElement;
}

describe('VerificationReportComponent', () => {
  beforeEach(() =>
    TestBed.configureTestingModule({
      imports: [VerificationReportComponent],
      providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()],
    }),
  );

  it('before finalization shows review-pending and NO overall truth badge', () => {
    const el = render(base());
    expect(el.textContent).toContain('Expert review pending.');
    expect(el.textContent).toContain('Under review');
    expect(el.querySelector('app-voting-details')).toBeNull();
    const badgeTexts = Array.from(el.querySelectorAll('.badge')).map((b) =>
      (b.textContent ?? '').replace(/[^A-Za-z]/g, ''),
    );
    expect(
      badgeTexts.some((t) => ['Fake', 'Real', 'Misleading', 'Altered'].includes(t)),
    ).toBeFalse();
  });

  it('after finalization shows the final decision apart from the preliminary findings, with Voting Details', () => {
    const el = render(
      base({
        is_finalized: true,
        review_pending: false,
        overall_verdict: 'MISLEADING',
        headline_status: 'EXACT_MATCHED',
      }),
    );
    const decision = el.querySelector('.decision-panel')!.textContent!;
    expect(decision).toContain('Final decision');
    expect(decision).toContain('Misleading');
    expect(decision).toContain('Decided by the expert reviewers');
    expect(el.querySelector('app-voting-details button')?.textContent).toContain('Voting Details');
    expect(el.querySelector('.report-summary')!.textContent).toContain('Headline: Exact Matched');
  });

  it('marks an administrator final decision', () => {
    const el = render(
      base({
        is_finalized: true,
        review_pending: false,
        overall_verdict: 'FAKE',
        decided_by_admin: true,
      }),
    );
    expect(el.querySelector('.decision-panel')!.textContent).toContain(
      'administrator made this final decision',
    );
  });

  it('labels the source finding "Relevant article from claimed source" with Found / Not Found', () => {
    expect(render(base()).querySelector('.findings-grid')!.textContent).toContain(
      'Relevant article from claimed source: Found',
    );
    expect(render(base()).textContent).not.toContain('01 / SOURCE');
  });

  it('shows the date comparison only when a date was claimed', () => {
    expect(render(base({ date_status: 'MISMATCHED' })).textContent).not.toContain(
      'Date: Mismatched',
    );
    expect(
      render(base({ date_status: 'MISMATCHED', claimed_published_date: '2026-01-02' })).textContent,
    ).toContain('Date: Mismatched');
  });

  it('labels the finding "Headline Alteration", never "Content Alteration"', () => {
    const el = render(base());
    expect(el.textContent).toContain('HEADLINE ALTERATION');
    expect(el.textContent).not.toMatch(/content alteration/i);
  });

  it('shows claim headline, source title, publisher, reason and exact match', () => {
    const el = render(base());
    const compare = el.querySelector('.headline-compare')!.textContent!;
    expect(compare).toContain('নতুন সেতুর উদ্বোধন');
    expect(compare).toContain('prothomalo.com');
    expect(el.querySelector('.headline-verdict')?.textContent).toContain('Exact Matched');
    expect(el.textContent).toContain('exactly matches the source title');
  });

  it('an altered headline lists each difference with the claim and source text', () => {
    const el = render(
      base({
        content_status: 'ALTERED',
        ai_content_status: 'ALTERED',
        analysis: {
          headline_alteration: {
            ...MATCHED_DETAIL,
            verdict: 'ALTERED',
            exact_match: false,
            reason: 'The headline states ১০ জন; the source title states ৫ জন.',
            differences: [
              {
                kind: 'numbers',
                detail: 'The headline states ১০ জন; the source title states ৫ জন.',
                claim_text: '১০ জন',
                source_text: '৫ জন',
              },
            ],
          },
        },
      }),
    );
    const diff = el.querySelector('.difference')!.textContent!;
    expect(diff).toContain('Number changed');
    expect(diff).toContain('১০ জন');
    expect(diff).toContain('৫ জন');
  });

  it('a missing headline verdict explains why instead of showing matched/altered', () => {
    const el = render(
      base({
        content_status: null,
        headline_check_status: 'MODEL_UNAVAILABLE',
        analysis: {
          headline_alteration: {
            ...MATCHED_DETAIL,
            status: 'MODEL_UNAVAILABLE',
            verdict: null,
            exact_match: false,
            reason: 'The semantic model was unavailable, so no verdict was reached.',
          },
        },
      }),
    );
    expect(el.querySelector('.headline-verdict')?.textContent).toContain('No verdict');
    const verdicts =
      el.querySelector('.findings-grid')!.textContent! +
      el.querySelector('.headline-verdict')!.textContent!;
    expect(verdicts).not.toMatch(/Exact Matched|Meaning Preserved|Headline: Altered/);
  });

  it('a missing article says "Not found in claimed source" and hides headline, date and body findings', () => {
    const el = render(
      base({
        source_status: 'NOT_FOUND',
        content_status: null,
        headline_check_status: 'SOURCE_NOT_FOUND',
        date_status: 'MATCHED',
        claimed_published_date: '2026-01-02',
        claim_scope: 'HEADLINE_WITH_BODY',
        analysis: null,
      }),
    );
    const text = el.textContent!;
    expect(text).toContain('Relevant article from claimed source: Not Found');
    expect(text).toContain('Not found in claimed source');
    expect(text).not.toMatch(/\?\s*Not found/i);
    expect(text).toContain('does not prove the news is false');
    expect(text).not.toContain('HEADLINE ALTERATION');
    expect(text).not.toContain('BODY SIMILARITY');
    expect(text).not.toContain('Date:');
  });

  it('headline-only claims show no body similarity section', () => {
    const el = render(base());
    expect(el.textContent).not.toContain('BODY SIMILARITY');
    expect(el.textContent).toContain('Headline only');
  });

  it('text with body shows the four labelled scores in their own section, and unavailable is not 0', () => {
    const el = render(
      base({
        claim_scope: 'HEADLINE_WITH_BODY',
        analysis: {
          headline_alteration: MATCHED_DETAIL,
          body_similarity: {
            status: 'COMPUTED',
            tfidf_cosine: { available: true, value: 0.9 },
            jaccard: { available: true, value: 0.32 },
            normalized_levenshtein: { available: true, value: 0.55 },
            semantic_cosine: { available: false, value: null, reason: 'embedding model failed' },
          },
        },
      }),
    );
    const cards = Array.from(el.querySelectorAll('.metric-card'));
    expect(cards.length).toBe(4);
    expect(el.textContent).toContain('TF-IDF cosine similarity');
    expect(el.textContent).toContain('Normalized Levenshtein similarity');
    expect(cards[0].textContent).toContain('90%');
    expect(cards[0].textContent).toContain('High similarity');
    expect(cards[3].textContent).toContain('Unavailable');
    expect(cards[3].textContent).not.toContain('0%');
    expect(el.textContent).toContain('not part of the Headline Alteration verdict');
  });

  it('body section explains why scores are unavailable', () => {
    const el = render(
      base({
        claim_scope: 'HEADLINE_WITH_BODY',
        analysis: {
          headline_alteration: MATCHED_DETAIL,
          body_similarity: {
            status: 'UNAVAILABLE',
            reason: 'The source article’s body could not be extracted.',
          },
        },
      }),
    );
    expect(el.textContent).toContain('Body similarity unavailable');
    expect(el.querySelectorAll('.metric-card').length).toBe(0);
  });

  it('a failed search shows coverage and no headline comparison verdict', () => {
    const el = render(
      base({
        source_status: 'INCOMPLETE',
        content_status: null,
        headline_check_status: 'SOURCE_CHECK_INCOMPLETE',
        confidence: 0,
        analysis: {
          search: {
            attempted: 5,
            success: 0,
            success_empty: 0,
            failed: 5,
            skipped: 0,
            cached: 0,
            adequate: false,
          },
        },
      }),
    );
    expect(el.textContent).toContain('Some searches were unavailable');
    expect(el.textContent).toContain('No conclusion can be drawn');
    expect(el.textContent).toContain('could not be completed');
  });

  it('legacy results never show an old content verdict as a headline verdict', () => {
    const el = render(
      base({
        content_status: null,
        ai_content_status: null,
        headline_check_status: null,
        legacy_result: true,
        analysis: null,
      }),
    );
    expect(el.textContent).toContain('earlier version of the checker');
    expect(el.querySelector('.findings-grid')!.textContent).not.toMatch(
      /Exact Matched|Meaning Preserved/,
    );
  });

  it('reviewers can inspect correspondence measurements; the public view does not show them', () => {
    const analysis = {
      headline_alteration: MATCHED_DETAIL,
      metrics: { headline_title_similarity: { state: 'COMPUTED' as const, value: 0.74 } },
    };
    expect(render(base({ analysis }), true).textContent).toContain(
      'Source correspondence measurements',
    );
    expect(render(base({ analysis })).textContent).not.toContain(
      'Source correspondence measurements',
    );
  });

  it('keeps the evidence link', () => {
    const el = render(
      base({
        matched_articles: [
          { url: 'https://prothomalo.com/a/b', title: 'T', rank_score: 0.8 } as any,
        ],
      }),
    );
    expect(el.querySelector('a.article-title')?.getAttribute('href')).toBe(
      'https://prothomalo.com/a/b',
    );
  });

  it('verified-sources mode: says so, shows up to three articles, primary first and marked', () => {
    const art = (n: number, primary = false) => ({
      url: `https://www.jugantor.com/national/${n}`,
      title: `Article ${n}`,
      publisher: 'jugantor.com',
      is_primary: primary,
    });
    const el = render(
      base({
        verification_mode: 'VERIFIED_SOURCES',
        source_resolution_reason: 'SOURCE_NOT_SUPPLIED',
        matched_articles: [art(1), art(2), art(3), art(4, true)],
      }),
    );
    const text = el.textContent ?? '';
    expect(text).toContain('Relevant articles from verified sources');
    expect(text).toContain('Related reports found in verified sources');
    expect(text).toContain('No claimed outlet was selected');
    expect(text).toContain('Compared with the selected verified-source article');
    expect(text).not.toContain('Relevant article from claimed source');
    const cards = el.querySelectorAll('.article-card');
    expect(cards.length).toBe(3);
    expect(cards[0].textContent).toContain('Article 4');
    expect(cards[0].querySelector('.primary-marker')).not.toBeNull();
    expect(cards[1].querySelector('.primary-marker')).toBeNull();
  });

  it('verified-sources NOT_FOUND never says "claimed source"', () => {
    const el = render(
      base({
        verification_mode: 'VERIFIED_SOURCES',
        source_status: 'NOT_FOUND',
        content_status: null,
        headline_check_status: 'SOURCE_NOT_FOUND',
      }),
    );
    const text = el.textContent ?? '';
    expect(text).toContain('No matching report was found in the verified sources searched');
    expect(text).not.toContain('Not found in claimed source');
  });
});
