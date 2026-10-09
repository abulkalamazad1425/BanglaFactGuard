export const DEFAULTS = {
  enabled: true,
  notifications: true,
  api: 'http://localhost:8000/api/v1',
  website: 'http://localhost:4200',
};
export const EMPTY_DRAFT = {
  type: 'SOURCE_BASED',
  headline: '',
  body_text: '',
  claimed_source_text: '',
  published_date: '',
};
export const ownerOf = (auth) => auth?.user?.id || 'guest';
export const terminal = (status) => ['FINALIZED', 'FAILED'].includes(status);
export const ready = (status) => ['EXPERT_REVIEW', 'FINALIZED', 'ESCALATED'].includes(status);
// Input modes, in the order shown everywhere (same as the website).
export const MODES = [
  ['SOURCE_BASED', 'Text & source'],
  ['PHOTO_CARD', 'Photo card'],
  ['MULTIMODAL', 'Text & image'],
];

/** A failed API call, keeping the HTTP status and the structured detail. */
export class HttpError extends Error {
  constructor(message, status, detail) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}
/** True only for the server's own "this submission does not exist" answer
 *  (HTTP 404 naming this very submission) - never for a generic 404 from a
 *  wrong API address, an outage or a network error. */
export const isDeletedOnServer = (error, id) =>
  error?.status === 404 &&
  error.detail?.error === 'not_found' &&
  String(error.detail?.submission_id) === String(id);
/** How long until an Activity item is re-checked. Finished items are still
 *  re-checked so that a submission deleted on the server disappears here. */
export const recheckDelay = (status) =>
  terminal(status) ? 10 * 60000 : ready(status) ? 5 * 60000 : 30000;
// Applied to fresh responses and cached Activity entries from older builds.
export const withoutDateWarnings = (warnings) =>
  (warnings || []).filter(
    (w) => !/\b(?:dates?|years?|months?|source|outlet|publisher)\b|তারিখ/i.test(w),
  );

// Same words as the website (frontend/src/app/shared/utils/status-labels.ts)
// and backend (app/shared/status_labels.py). Stored API values never change.
export const NOT_FOUND_IN_CLAIMED_SOURCE = 'Not found in claimed source';
/** A claim without a usable outlet is checked against the verified sources. */
export const NOT_FOUND_IN_VERIFIED_SOURCES = 'Not found in verified sources';
export const HEADLINE_LABELS = {
  EXACT_MATCHED: 'Exact Matched',
  MEANING_PRESERVED: 'Meaning Preserved',
  ALTERED: 'Altered',
};
export const DATE_LABELS = {
  MATCHED: 'Matched',
  MISMATCHED: 'Mismatched',
  INCOMPLETE: 'Could not be determined',
};
export const OVERALL_LABELS = {
  REAL: 'Real',
  FAKE: 'Fake',
  MISLEADING: 'Misleading',
  ALTERED: 'Altered',
};
export const aiDecisionLabel = (prediction) =>
  !prediction ? null : String(prediction).toUpperCase() === 'FAKE' ? 'Likely Fake' : 'Likely Real';

/** First five whitespace-separated words, with "..." only when there are more. */
export function headlinePreview(headline, words = 5) {
  const tokens = String(headline || '')
    .normalize('NFC')
    .split(/\s+/u)
    .filter(Boolean);
  return tokens.slice(0, words).join(' ') + (tokens.length > words ? '...' : '');
}

function headlineStatus(result) {
  if (result.headline_status) return result.headline_status;
  if (result.content_status === 'ALTERED') return 'ALTERED';
  if (result.content_status === 'MATCHED') {
    const d = result.analysis?.headline_alteration;
    return d?.exact_match || d?.basis === 'exact' ? 'EXACT_MATCHED' : 'MEANING_PRESERVED';
  }
  return null;
}

/**
 * Activity summary. Preliminary view rules: never a "found" source status;
 * a missing article shows only "Not found in claimed source" (no headline or
 * date); the headline status is Exact Matched / Meaning Preserved / Altered;
 * the date comparison only when a date was claimed. The text & image model's
 * call is "AI decision: Likely Fake/Real". A final decision is the reviewers'
 * (or an admin's) overall verdict and is never mixed with the AI call.
 * Individual reviewer votes are never shown here.
 */
export function summarize(type, data, lookup = {}) {
  const result =
    type === 'PHOTO_CARD' ? data.verification : type === 'SOURCE_BASED' ? data.result : data;
  const status = data.status || lookup.status || 'EXPERT_REVIEW';
  const final = result?.overall_verdict || result?.expert_overall_verdict;
  const lines = [];
  if (result && type !== 'MULTIMODAL') {
    if (result.source_status === 'NOT_FOUND')
      lines.push(
        result.verification_mode === 'VERIFIED_SOURCES'
          ? NOT_FOUND_IN_VERIFIED_SOURCES
          : NOT_FOUND_IN_CLAIMED_SOURCE,
      );
    else if (result.source_status === 'INCOMPLETE') lines.push('Source check incomplete');
    else if (result.source_status === 'CONFIRMED') {
      const hs = headlineStatus(result);
      lines.push(`Headline: ${hs ? HEADLINE_LABELS[hs] : 'No verdict'}`);
      const claimedDate =
        result.claimed_published_date || data.published_date || lookup.published_date;
      if (claimedDate && result.date_status)
        lines.push(`Date: ${DATE_LABELS[result.date_status] || result.date_status}`);
    }
  }
  if (result?.prediction && type === 'MULTIMODAL')
    lines.push(`AI decision: ${aiDecisionLabel(result.prediction)}`);
  if (final) lines.unshift(`Final decision: ${OVERALL_LABELS[final] || final}`);
  return {
    status,
    stage:
      status === 'FAILED'
        ? 'failed'
        : final && status === 'FINALIZED'
          ? `final:${final}`
          : result && ready(status)
            ? 'preliminary'
            : null,
    phase: data.phase || lookup.processing_phase,
    lines,
    headline: data.headline || lookup.headline,
    error: data.error || data.failure_reason || lookup.failure_reason,
    warnings: type === 'PHOTO_CARD' ? [] : data.extraction_warnings || [],
    final: Boolean(final),
    review: final ? 'Final decision made by reviewers' : 'Under review — preliminary AI result',
  };
}

/** A validation error that names the field it belongs to, so the panel can show it there. */
export class FieldError extends Error {
  constructor(field, message) {
    super(message);
    this.field = field;
  }
}

// Required fields (same as the website and the API):
//   Text & source (SOURCE_BASED): headline (5+ characters), claimed news outlet
//   Photo card   (PHOTO_CARD):    photocard image only - the headline, outlet and
//                                 date are read from the card on the server
//   Text & image (MULTIMODAL):    headline, article text (10+ characters), image
export function validateDraft(d, image) {
  if (d.type !== 'PHOTO_CARD' && d.headline.trim().length < (d.type === 'SOURCE_BASED' ? 5 : 1))
    throw new FieldError(
      'headline',
      d.type === 'SOURCE_BASED'
        ? 'Enter the headline (at least 5 characters).'
        : 'Enter the headline.',
    );
  if (d.headline.length > 2000)
    throw new FieldError('headline', 'Headline limit is 2,000 characters.');
  if (d.body_text.length > 50000)
    throw new FieldError('body_text', 'Article text limit is 50,000 characters.');
  if (d.type === 'MULTIMODAL' && d.body_text.trim().length < 10)
    throw new FieldError('body_text', 'Enter the article text (at least 10 characters).');
  if (d.type !== 'SOURCE_BASED' && !image)
    throw new FieldError(
      'image',
      d.type === 'PHOTO_CARD'
        ? 'Add the photocard image: upload it or select a screenshot area.'
        : 'Add the image: upload it or select a screenshot area.',
    );
  if (
    d.type !== 'SOURCE_BASED' &&
    image &&
    (!image.size ||
      image.size > 10 * 1024 * 1024 ||
      !['image/png', 'image/jpeg', 'image/webp', 'image/gif'].includes(image.type))
  )
    throw new FieldError('image', 'Image must be a PNG, JPEG, WebP or GIF up to 10 MB.');
}
export function cropRect(rect, view, bitmap) {
  const x = Math.max(0, Math.min(rect.x, view.width));
  const y = Math.max(0, Math.min(rect.y, view.height));
  return {
    x: Math.round((x * bitmap.width) / view.width),
    y: Math.round((y * bitmap.height) / view.height),
    width: Math.max(
      1,
      Math.round((Math.min(rect.width, view.width - x) * bitmap.width) / view.width),
    ),
    height: Math.max(
      1,
      Math.round((Math.min(rect.height, view.height - y) * bitmap.height) / view.height),
    ),
  };
}

/** Normalises lines cached by older builds to the current wording. Returns
 *  null for a line that must no longer be shown (a "found" source status). */
export function resultLine(line) {
  if (/^Source: (?:Confirmed|Found in claimed source|CONFIRMED)$/.test(line)) return null;
  return line
    .replace(
      /AI prediction: (?:NON_FAKE|REAL|Likely real)(?: \(preliminary\))?/,
      'AI decision: Likely Real',
    )
    .replace(/AI prediction: (?:FAKE|Likely fake)(?: \(preliminary\))?/, 'AI decision: Likely Fake')
    .replace(
      /(?:Expert|Final) verdict: (\w+)/,
      (_, v) => `Final decision: ${v[0].toUpperCase() + v.slice(1).toLowerCase()}`,
    )
    .replace(
      /^Source: (?:Not found in claimed source|Not found|NOT_FOUND)$/,
      NOT_FOUND_IN_CLAIMED_SOURCE,
    )
    .replace(/^Source: Check incomplete$/, 'Source check incomplete')
    .replace(/^Headline Alteration: Matched$/, 'Headline: Meaning Preserved')
    .replace(/^Headline Alteration: /, 'Headline: ')
    .replace('Date: Date mismatch', 'Date: Mismatched');
}
