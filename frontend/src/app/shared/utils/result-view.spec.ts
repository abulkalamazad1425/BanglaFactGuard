import { ManipulationFlags } from '../../models/verification.model';
import { buildCheckRows, buildScoreRows, hasBody, strengthFor } from './result-view';

describe('result-view', () => {
  describe('buildCheckRows', () => {
    it('shows only COMPLETED PASSING checks as green; unrun checks are neutral, not passes', () => {
      const flags: ManipulationFlags = {
        check_states: {
          headline: 'PASSED',
          body: 'NOT_APPLICABLE',
          numbers: 'NOT_EVALUATED',
          negation: 'PASSED',
          entities: 'NOT_EVALUATED',
          scope: 'NOT_APPLICABLE',
        },
      };
      const rows = buildCheckRows(flags, 'HEADLINE_ONLY');
      const byKey = Object.fromEntries(rows.map((r) => [r.key, r]));
      expect(byKey['headline'].cls).toBe('passed');
      expect(byKey['negation'].icon).toBe('✓');
      expect(byKey['numbers'].cls).toBe('unknown');
      expect(byKey['numbers'].icon).toBe('—');
      expect(byKey['entities'].cls).toBe('unknown');
      expect(rows.some((r) => r.cls === 'passed' && r.state !== 'PASSED')).toBeFalse();
    });

    it('never shows a body check for a photo card / headline-only claim, even if one is present', () => {
      const flags: ManipulationFlags = { check_states: { headline: 'PASSED', body: 'PASSED' } };
      expect(buildCheckRows(flags, 'HEADLINE_ONLY').map((r) => r.key)).not.toContain('body');
      expect(buildCheckRows(flags, 'HEADLINE_WITH_BODY').map((r) => r.key)).toContain('body');
    });

    it('omits NOT_APPLICABLE checks', () => {
      const flags: ManipulationFlags = { check_states: { headline: 'PASSED', numbers: 'NOT_APPLICABLE' } };
      expect(buildCheckRows(flags, 'HEADLINE_ONLY').map((r) => r.key)).toEqual(['headline']);
    });

    it('a failed check carries the quoted discrepancy', () => {
      const flags: ManipulationFlags = {
        check_states: { numbers: 'FAILED' },
        discrepancies: [
          { kind: 'numbers', claim_text: 'বন্যায় ৫ জন নিহত', evidence_text: 'বন্যায় ১০ জন নিহত', detail: 'claimed 5, source states 10', part: 'headline' },
        ],
      };
      const [row] = buildCheckRows(flags, 'HEADLINE_ONLY');
      expect(row.cls).toBe('failed');
      expect(row.icon).toBe('✗');
      expect(row.discrepancies.length).toBe(1);
      expect(row.discrepancies[0].evidence_text).toContain('১০');
    });

    it('historical rows with no recorded states never show greens', () => {
      const rows = buildCheckRows({ headline_manipulated: false, body_altered: false }, 'HEADLINE_ONLY');
      expect(rows.length).toBe(1);
      expect(rows[0].state).toBe('NOT_RECORDED');
      expect(rows[0].cls).toBe('unknown');
    });

    it('historical rows still surface a legacy flag that WAS set', () => {
      const rows = buildCheckRows({ numbers_altered: true }, 'HEADLINE_ONLY');
      expect(rows.some((r) => r.key === 'numbers' && r.cls === 'failed')).toBeTrue();
    });
  });

  describe('buildScoreRows', () => {
    it('never renders a Body Match for a headline-only claim, even if a legacy value is present', () => {
      const rows = buildScoreRows({ headline_similarity: 0.9, body_similarity: 0.12 }, null, 'HEADLINE_ONLY');
      expect(rows.map((r) => r.key)).not.toContain('body_similarity');
      expect(rows.map((r) => r.key)).not.toContain('body_keyword_coverage');
    });

    it('shows body metrics for text with a submitted body', () => {
      const rows = buildScoreRows({ headline_similarity: 0.9, body_similarity: 0.8 }, null, 'HEADLINE_WITH_BODY');
      expect(rows.find((r) => r.key === 'body_similarity')?.display).toBe('80.0%');
    });

    it('renders unknown scores as not applicable / unavailable, never 0% or 100%', () => {
      const rows = buildScoreRows(
        { headline_similarity: 0.9, entity_match: null, numerical_consistency: null },
        {
          metrics: {
            entity_match: { state: 'UNAVAILABLE', reason: 'NER unavailable' },
            numerical_consistency: { state: 'NOT_APPLICABLE', reason: 'claim contains no numbers' },
          },
          passages: [], source_basis: [], content_basis: [],
        },
        'HEADLINE_ONLY',
      );
      const ent = rows.find((r) => r.key === 'entity_match')!;
      const num = rows.find((r) => r.key === 'numerical_consistency')!;
      expect(ent.value).toBeNull();
      expect(ent.display).toBe('Unavailable');
      expect(ent.note).toBe('NER unavailable');
      expect(num.display).toBe('Not applicable');
      expect(rows.every((r) => r.display !== '0.0%' && r.display !== '100.0%' || r.value !== null)).toBeTrue();
    });

    it('a genuine zero is shown as 0.0%', () => {
      const rows = buildScoreRows({ headline_keyword_coverage: 0 }, null, 'HEADLINE_ONLY');
      expect(rows.find((r) => r.key === 'headline_keyword_coverage')?.display).toBe('0.0%');
    });
  });

  it('hasBody / strengthFor', () => {
    expect(hasBody('HEADLINE_WITH_BODY')).toBeTrue();
    expect(hasBody('HEADLINE_ONLY')).toBeFalse();
    expect(hasBody(undefined)).toBeFalse();
    expect(strengthFor(0.8, 'CONFIRMED')).toBe('80%');
    expect(strengthFor(0, 'INCOMPLETE')).toBe('—');
  });
});
