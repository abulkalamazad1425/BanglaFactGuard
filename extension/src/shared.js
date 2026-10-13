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
export const MODES = [
  ['SOURCE_BASED', 'Text & source'],
  ['PHOTO_CARD', 'Photo card'],
  ['MULTIMODAL', 'Text & image'],
];

export class HttpError extends Error {
  constructor(message, status, detail) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}
export const isDeletedOnServer = (error, id) =>
  error?.status === 404 &&
  error.detail?.error === 'not_found' &&
  String(error.detail?.submission_id) === String(id);
export const recheckDelay = (status) =>
  terminal(status) ? 10 * 60000 : ready(status) ? 5 * 60000 : 30000;
export const withoutDateWarnings = (warnings) =>
  (warnings || []).filter(
    (w) => !/\b(?:dates?|years?|months?|source|outlet|publisher)\b|তারিখ/i.test(w),
  );

export const NOT_FOUND_IN_CLAIMED_SOURCE = 'Not found in claimed source';
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
  if (type === 'MULTIMODAL' && result?.original_submission_id)
    lines.push("Already checked earlier: showing that claim's result");
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

export class FieldError extends Error {
  constructor(field, message) {
    super(message);
    this.field = field;
  }
}

export function validateDraft(d, image) {
  if (d.type === 'SOURCE_BASED' && d.headline.trim().length < 5)
    throw new FieldError('headline', 'Enter the headline (at least 5 characters).');
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

export const ACTIVITY_STATUS = {
  PENDING: 'Queued',
  PROCESSING: 'Checking your claim',
  EXPERT_REVIEW: 'Preliminary result ready',
  FINALIZED: 'Final decision ready',
  ESCALATED: 'Preliminary result ready · under review',
  FAILED: 'Verification could not finish',
};

export const ACTIVITY_PAGE_SIZE = 10;

const fold = (text) =>
  String(text ?? '')
    .normalize('NFC')
    .toLocaleLowerCase();

export function searchActivity(items, query) {
  const words = fold(query).split(/\s+/).filter(Boolean);
  if (!words.length) return items;
  return items.filter((item) => {
    const text = fold(
      [
        item.headline,
        item.summary?.headline,
        item.type?.replaceAll('_', ' '),
        ACTIVITY_STATUS[item.status],
        ...(item.summary?.lines || []).map(resultLine),
      ]
        .filter(Boolean)
        .join(' \n '),
    );
    return words.every((word) => text.includes(word));
  });
}

export function paginate(items, page, size = ACTIVITY_PAGE_SIZE) {
  const pages = Math.max(1, Math.ceil(items.length / size));
  const current = Math.min(Math.max(1, page || 1), pages);
  return {
    items: items.slice((current - 1) * size, current * size),
    page: current,
    pages,
    total: items.length,
  };
}
