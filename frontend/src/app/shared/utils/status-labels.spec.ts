import { aiDecisionLabel, preliminaryChips } from './status-labels';

describe('status labels', () => {
  it('never shows "Found" in a summary, only "Not found in claimed source"', () => {
    const found = preliminaryChips({ source_status: 'CONFIRMED', headline_status: 'EXACT_MATCHED' });
    expect(found.map(c => c.value)).toEqual(['Exact Matched']);
    expect(found.some(c => /found/i.test(c.value))).toBeFalse();

    const missing = preliminaryChips({ source_status: 'NOT_FOUND', headline_status: null, date_status: 'MATCHED', claimed_date: '2026-01-01' });
    expect(missing.map(c => c.value)).toEqual(['Not found in claimed source']);
  });

  it('shows the date comparison only when a date was claimed', () => {
    const withDate = preliminaryChips({ source_status: 'CONFIRMED', headline_status: 'MEANING_PRESERVED', date_status: 'MISMATCHED', claimed_date: '2026-01-01' });
    expect(withDate.map(c => c.value)).toEqual(['Meaning Preserved', 'Mismatched']);
    const withoutDate = preliminaryChips({ source_status: 'CONFIRMED', headline_status: 'ALTERED', date_status: 'MISMATCHED', claimed_date: null });
    expect(withoutDate.map(c => c.value)).toEqual(['Altered']);
  });

  it('maps the model label to Likely Fake / Likely Real', () => {
    expect(aiDecisionLabel('FAKE')).toBe('Likely Fake');
    expect(aiDecisionLabel('NON_FAKE')).toBe('Likely Real');
    expect(aiDecisionLabel(null)).toBeNull();
  });
});
