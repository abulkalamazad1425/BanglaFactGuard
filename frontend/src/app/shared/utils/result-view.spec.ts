import { BodySimilarityReport, VerificationResponse } from '../../models/verification.model';
import {
  bodySectionMessage,
  buildBodyMetricRows,
  buildCorrespondenceRows,
  differenceLabel,
  hasBody,
  headlineView,
  scoreBand,
} from './result-view';

function response(overrides: Partial<VerificationResponse> = {}): VerificationResponse {
  return {
    submission_id: 's1',
    source_status: 'CONFIRMED',
    content_status: 'MATCHED',
    headline_check_status: 'COMPLETED',
    confidence: 0.9,
    reasoning: '',
    matched_articles: [],
    cached: false,
    created_at: '2026-10-05T00:00:00Z',
    ...overrides,
  };
}

describe('result-view', () => {
  describe('headlineView', () => {
    it('splits a match into Exact Matched / Meaning Preserved and keeps Altered', () => {
      expect(headlineView(response({ headline_status: 'EXACT_MATCHED' })).title).toBe(
        'Exact Matched',
      );
      expect(headlineView(response({ headline_status: 'MEANING_PRESERVED' })).title).toBe(
        'Meaning Preserved',
      );
      expect(
        headlineView(response({ content_status: 'ALTERED', headline_status: 'ALTERED' })).title,
      ).toBe('Altered');
      // An older response without headline_status: no evidence of exactness -> Meaning Preserved.
      expect(headlineView(response()).title).toBe('Meaning Preserved');
      expect(headlineView(response({ content_status: 'ALTERED' })).tone).toBe('altered');
    });

    it('explains a missing verdict instead of guessing one', () => {
      const v = headlineView(
        response({ content_status: null, headline_check_status: 'UNDETERMINED' }),
      );
      expect(v.tone).toBe('none');
      expect(v.title).toBe('No verdict');
      expect(v.summary).toContain('no verdict');
    });

    it('keeps source-not-found and a failed search apart', () => {
      const notFound = headlineView(
        response({
          source_status: 'NOT_FOUND',
          content_status: null,
          headline_check_status: 'SOURCE_NOT_FOUND',
        }),
      );
      const failed = headlineView(
        response({
          source_status: 'INCOMPLETE',
          content_status: null,
          headline_check_status: 'SOURCE_CHECK_INCOMPLETE',
        }),
      );
      expect(notFound.summary).toContain('No relevant article');
      expect(failed.summary).toContain('could not be completed');
      expect(notFound.summary).not.toEqual(failed.summary);
    });

    it('never relabels a legacy content verdict as a headline verdict', () => {
      const v = headlineView(
        response({ content_status: null, headline_check_status: null, legacy_result: true }),
      );
      expect(v.tone).toBe('none');
      expect(v.summary).toContain('earlier version');
    });
  });

  describe('body metric rows', () => {
    const report: BodySimilarityReport = {
      status: 'COMPUTED',
      tfidf_cosine: { available: true, value: 0.82 },
      jaccard: { available: true, value: 0.31 },
      normalized_levenshtein: {
        available: true,
        value: 0.55,
        details: { truncated: true, claim_chars_compared: 20000, source_chars_compared: 20000 },
      },
      semantic_cosine: { available: false, value: null, reason: 'embedding model failed' },
    };

    it('labels every metric with its range and explanation', () => {
      const rows = buildBodyMetricRows(report);
      expect(rows.map((r) => r.key)).toEqual([
        'tfidf_cosine',
        'jaccard',
        'normalized_levenshtein',
        'semantic_cosine',
      ]);
      expect(rows[0].label).toBe('TF-IDF cosine similarity');
      expect(rows.every((r) => r.range.includes('0 =') && r.measures.length > 20)).toBeTrue();
      expect(rows[3].label).toContain('LaBSE');
      expect(rows[3].label).not.toContain('BERTScore');
    });

    it('shows a failed metric as unavailable with its reason, never as 0', () => {
      const sem = buildBodyMetricRows(report)[3];
      expect(sem.available).toBeFalse();
      expect(sem.value).toBeNull();
      expect(sem.display).toBe('Unavailable');
      expect(sem.note).toBe('embedding model failed');
      expect(buildBodyMetricRows(report)[0].display).toBe('82%');
    });

    it('keeps successful scores when another metric fails and notes truncation', () => {
      const rows = buildBodyMetricRows(report);
      expect(rows.filter((r) => r.available).length).toBe(3);
      expect(rows[2].note).toContain('first 20000');
    });

    it('describes bands without implying truth', () => {
      expect(scoreBand(0.8)).toBe('High');
      expect(scoreBand(0.5)).toBe('Moderate');
      expect(scoreBand(0.1)).toBe('Low');
    });

    it('a skipped comparison has no rows, and unavailable reasons are surfaced', () => {
      expect(buildBodyMetricRows({ status: 'SKIPPED', reason: 'no body' })).toEqual([]);
      expect(
        bodySectionMessage(
          { status: 'UNAVAILABLE', reason: 'The source body could not be extracted.' },
          'HEADLINE_WITH_BODY',
        ),
      ).toBe('The source body could not be extracted.');
      expect(bodySectionMessage(report, 'HEADLINE_WITH_BODY')).toBeNull();
      expect(bodySectionMessage(report, 'HEADLINE_ONLY')).toBeNull();
    });
  });

  it('labels each kind of headline difference', () => {
    expect(differenceLabel('subject_object')).toContain('who did what to whom');
    expect(differenceLabel('main_point')).toBe('Main statement differs');
    expect(differenceLabel('something-new')).toBe('Meaningful difference');
  });

  it('correspondence measurements never render a missing value as 0%', () => {
    const rows = buildCorrespondenceRows({
      metrics: {
        headline_title_similarity: { state: 'COMPUTED', value: 0.74 },
        title_keyword_coverage: {
          state: 'UNAVAILABLE',
          value: null,
          reason: 'source article has no title',
        },
      },
    });
    expect(rows.map((r) => r.display)).toEqual(['74%', 'Unavailable']);
  });

  it('body applies only to claims with a submitted body', () => {
    expect(hasBody('HEADLINE_WITH_BODY')).toBeTrue();
    expect(hasBody('HEADLINE_ONLY')).toBeFalse();
    expect(hasBody(null)).toBeFalse();
  });
});
