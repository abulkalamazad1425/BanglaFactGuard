import { predictionLabel, readableExplanation, requestError, verificationFailure } from './presentation';

describe('Public presentation mappings', () => {
  it('keeps service failure separate from a news verdict and hides raw diagnostics', () => {
    const failure = verificationFailure('GEMINI EXISTING_FALLBACK RuntimeError /api/verify');
    expect(failure).toContain('not a verdict');
    expect(failure).not.toMatch(/GEMINI|FALLBACK|RuntimeError|\/api/);
    expect(requestError({ status: 503 })).toContain('temporarily unavailable');
  });

  it('offers clearer-image recovery only for unreadable text', () => {
    expect(verificationFailure('No readable Bangla text could be found in the image.')).toContain('clearer image');
    expect(verificationFailure('Could not extract a readable headline from this photo card.')).toContain('enter the news text');
    expect(verificationFailure('image storage unavailable')).not.toContain('clearer image');
  });

  it('does not turn an unknown or absent prediction into a real-news verdict', () => {
    expect(predictionLabel('FAKE')).toBe('Likely Fake');
    expect(predictionLabel('NON_FAKE')).toBe('Likely Real');
    expect(predictionLabel('REAL')).toBe('Likely Real');
    expect(predictionLabel(null)).toBe('Result unavailable');
    expect(predictionLabel('FAILED')).toBe('Result unavailable');
  });

  it('keeps useful Bengali and evidence prose but removes diagnostic sentences', () => {
    expect(readableExplanation('খবরের দাবি ও উৎসের প্রতিবেদনে পার্থক্য আছে।')).toContain('পার্থক্য');
    const text = readableExplanation('The claimed number differs. GEMINI extraction failed. EXISTING_FALLBACK was used.');
    expect(text).toContain('The claimed number differs.');
    expect(text).not.toMatch(/GEMINI|FALLBACK/);
    expect(readableExplanation('PHOTO_CARD is in EXPERT_REVIEW.')).toBe('photocard is in awaiting expert review.');
  });

  it('gives status-specific recovery without exposing an endpoint or stack trace', () => {
    expect(requestError({ status: 0 })).toContain('connection');
    expect(requestError({ status: 413 })).toContain('10 MB');
    expect(requestError({ status: 429 })).toContain('wait');
  });
});
