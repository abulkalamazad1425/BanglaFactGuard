export const DEFAULTS = { enabled: true, notifications: true, api: 'http://localhost:8000/api/v1', website: 'http://localhost:4200' };
export const EMPTY_DRAFT = { type: 'SOURCE_BASED', headline: '', body_text: '', claimed_source_text: '', published_date: '' };
export const ownerOf = auth => auth?.user?.id || 'guest';
export const terminal = status => ['FINALIZED', 'FAILED'].includes(status);
export const ready = status => ['EXPERT_REVIEW', 'FINALIZED', 'ESCALATED'].includes(status);
// Applied to fresh responses and cached Activity entries from older builds.
export const withoutDateWarnings = warnings => (warnings || []).filter(w => !/\b(?:dates?|years?|months?|source|outlet|publisher)\b|তারিখ/i.test(w));
export function summarize(type, data, lookup = {}) {
  const result = type === 'PHOTO_CARD' ? data.verification : type === 'SOURCE_BASED' ? data.result : data;
  const status = data.status || lookup.status || 'EXPERT_REVIEW';
  const final = result?.overall_verdict || result?.expert_overall_verdict;
  const lines = [];
  const names = { CONFIRMED: 'Confirmed', NOT_FOUND: 'Not found', INCOMPLETE: 'Check incomplete', MATCHED: 'Matched', ALTERED: 'Altered', MISMATCHED: 'Date mismatch' };
  if (result && type !== 'MULTIMODAL') {
    lines.push(`Source: ${names[result.source_status] || 'Not assessed'}`);
    // Headline Alteration has only two verdicts; a confirmed source without one says so.
    if (result.content_status) lines.push(`Headline Alteration: ${names[result.content_status] || result.content_status}`);
    else if (result.source_status === 'CONFIRMED') lines.push('Headline Alteration: No verdict');
    if (result.date_status) lines.push(`Date: ${names[result.date_status] || result.date_status}`);
  }
  if (result?.prediction && type === 'MULTIMODAL') lines.push(`AI prediction: ${result.prediction === 'FAKE' ? 'Likely fake' : 'Likely real'}`);
  if (final) lines.unshift(`Final verdict: ${final.charAt(0) + final.slice(1).toLowerCase()}`);
  return { status, stage: status === 'FAILED' ? 'failed' : final && status === 'FINALIZED' ? `final:${final}` : result && ready(status) ? 'preliminary' : null,
    phase: data.phase || lookup.processing_phase, lines, headline: data.headline || lookup.headline,
    error: data.error || data.failure_reason || lookup.failure_reason,
    warnings: type === 'PHOTO_CARD' ? withoutDateWarnings(data.extraction_warnings) : data.extraction_warnings || [], final: Boolean(final),
    review: status === 'ESCALATED' ? 'Additional review required' : final ? 'Expert review complete' : 'Expert review pending' };
}
export function validateDraft(d, image) {
  if (d.type !== 'PHOTO_CARD' && d.headline.trim().length < (d.type === 'SOURCE_BASED' ? 5 : 1)) throw Error('Enter a valid headline. Source checks need at least 5 characters.');
  if (d.headline.length > 2000 || d.body_text.length > 50000) throw Error('Headline limit is 2,000 characters; body limit is 50,000.');
  if (d.type !== 'MULTIMODAL' && !d.claimed_source_text.trim()) throw Error('Enter the claimed news source.');
  if (d.type === 'MULTIMODAL' && d.body_text.trim().length < 10) throw Error('Multimodal analysis needs at least 10 characters of body text.');
  if (d.type !== 'SOURCE_BASED' && !image) throw Error('Upload an image or select a screenshot area.');
  if (d.type !== 'SOURCE_BASED' && image && (!image.size || image.size > 10 * 1024 * 1024 || !['image/png', 'image/jpeg', 'image/webp', 'image/gif'].includes(image.type))) throw Error('Image must be a PNG, JPEG, WebP or GIF up to 10 MB.');
}
export function cropRect(rect, view, bitmap) {
  const x = Math.max(0, Math.min(rect.x, view.width));
  const y = Math.max(0, Math.min(rect.y, view.height));
  return { x: Math.round(x * bitmap.width / view.width), y: Math.round(y * bitmap.height / view.height),
    width: Math.max(1, Math.round(Math.min(rect.width, view.width - x) * bitmap.width / view.width)),
    height: Math.max(1, Math.round(Math.min(rect.height, view.height - y) * bitmap.height / view.height)) };
}

export function resultLine(line) {
  return line.replace(/AI prediction: (?:NON_FAKE|REAL)(?: \(preliminary\))?/, 'AI prediction: Likely real')
    .replace(/AI prediction: FAKE(?: \(preliminary\))?/, 'AI prediction: Likely fake')
    .replace(/Expert verdict: (\w+)/, (_, v) => `Final verdict: ${v[0]+v.slice(1).toLowerCase()}`)
    .replace('Source: Found in claimed source', 'Source: Confirmed').replace('Source: Not found in claimed source', 'Source: Not found');
}
