/** Presentation-only mappings. Raw responses remain available to diagnostics. */
export function requestError(error: { status?: number }, fallback = 'Unable to complete this request. Please try again.'): string {
  switch (error?.status) {
    case 0: return 'Unable to connect. Check your connection and try again.';
    case 401: return 'Please check your sign-in details or sign in again.';
    case 403: return 'You do not have access to this action.';
    case 409: return 'This already exists. Check your details before trying again.';
    case 413: return 'The image is too large. Choose an image under 10 MB.';
    case 415: return 'Choose a supported image: JPEG, PNG, WebP or GIF.';
    case 422: return 'Check the required fields and image, then try again.';
    case 429: return 'Too many requests. Please wait a moment and try again.';
    default: return (error?.status ?? 0) >= 500
      ? 'This service is temporarily unavailable. Please try again shortly.' : fallback;
  }
}

export function verificationFailure(reason?: string | null): string {
  if (/no readable|readable headline|sharper|less cluttered/i.test(reason ?? '')) {
    return 'We could not read the headline. Upload a clearer image with the full Bengali headline visible, or enter the news text instead.';
  }
  return 'Verification could not be completed. Please try again. This is not a verdict about whether the news is true or false.';
}

/** The text & image model's preliminary call — never an expert verdict. */
export function predictionLabel(value?: string | null): string {
  const v = (value ?? '').toUpperCase();
  if (v === 'FAKE' || v === 'LIKELY FAKE') return 'Likely Fake';
  if (v === 'REAL' || v === 'NON_FAKE' || v === 'LIKELY REAL') return 'Likely Real';
  return 'Result unavailable';
}

/** Preserve evidence prose, replacing diagnostic sentences with a limitation. */
export function readableExplanation(value?: string | null): string {
  if (!value) return '';
  const terms: Record<string, string> = { SOURCE_BASED: 'source check', PHOTO_CARD: 'photocard', MULTIMODAL: 'text and image', EXPERT_REVIEW: 'awaiting expert review', FINALIZED: 'review complete', NOT_FOUND: 'not found in claimed source', INCOMPLETE: 'check incomplete', CONFIRMED: 'relevant article found in claimed source', MATCHED: 'matched', MISMATCHED: 'mismatched', REAL: 'real', FAKE: 'fake', ALTERED: 'altered', MISLEADING: 'misleading' };
  value = value.replace(/\b[A-Z][A-Z_]+\b/g, word => terms[word] ?? word);
  return value.split(/(?<=[.!?])\s+|\n/).map(sentence =>
    /gemini|existing_fallback|labse|deberta|banglabert|efficientnet|traceback|exception|\b(?:NLI|OCR|HTTP|API)\b|\b[A-Z]+_[A-Z_]+\b|embedding|token count|model.version|pipeline|extractor/i.test(sentence)
      ? 'Some automated checks have limitations; review the available source evidence before drawing a conclusion.'
      : sentence
  ).filter((sentence, index, all) => all.indexOf(sentence) === index).join(' ');
}
