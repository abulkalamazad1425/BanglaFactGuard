// ============================================================
// Photo Card Verification Models — synced with backend
// app/features/photocard/schemas.py
// ============================================================

import { VerificationResponse } from './verification.model';

/** Why a recognised line was excluded from the claim. */
export type NoiseReason =
  | 'social_cta'
  | 'byline'
  | 'credit'
  | 'timestamp'
  | 'engagement'
  | 'copyright'
  | 'advert'
  | 'source_banner'
  | 'url'
  | 'social_handle'
  | 'phone_number'
  | 'not_bangla'
  | 'too_short'
  | 'low_confidence'
  | 'no_letters'
  | 'empty';

export interface OcrLine {
  text: string;
  confidence?: number | null;
  bangla_ratio: number;
  is_noise: boolean;
  noise_reason?: NoiseReason | null;
}

export interface DetectedSource {
  source_id: string;
  canonical_name: string;
  display_name: string;
  display_name_en?: string | null;
  confidence: number;
  matched_text: string;
  /** How the branding was matched: 'domain' | 'exact' | 'fuzzy' */
  method: string;
}

/** Step 1 — POST /photocard/extract. Nothing is verified yet. */
export interface PhotoCardExtractResponse {
  draft_id: string;
  raw_text: string;
  cleaned_text: string;
  suggested_headline: string;
  suggested_body?: string | null;
  lines: OcrLine[];
  removed_line_count: number;
  detected_sources: DetectedSource[];
  primary_source?: DetectedSource | null;
  ocr_confidence?: number | null;
  ocr_engine: string;
  bangla_char_ratio: number;
  image_url?: string | null;
  warnings: string[];
  created_at: string;
}

/** Step 2 — POST /photocard/verify, carrying the text the user confirmed. */
export interface PhotoCardVerifyRequest {
  draft_id: string;
  headline: string;
  body_text?: string | null;
  claimed_source_text: string;
  published_date?: string | null; // YYYY-MM-DD
  force_refresh?: boolean;
}

export interface PhotoCardVerifyResponse {
  submission_id: string;
  verification: VerificationResponse;
  confirmed_headline: string;
  confirmed_body?: string | null;
  ocr_raw_text: string;
  ocr_engine: string;
  ocr_confidence?: number | null;
  image_url?: string | null;
  detected_source_confidence?: number | null;
  reused_previous_result: boolean;
  original_submission_id?: string | null;
}

/** GET /photocard/{submission_id} — a stored report. */
export interface PhotoCardResultResponse {
  submission_id: string;
  status: string;
  headline?: string | null;
  body_text?: string | null;
  claimed_source_text?: string | null;
  published_date?: string | null;
  ocr_raw_text?: string | null;
  ocr_confirmed_text?: string | null;
  ocr_engine?: string | null;
  ocr_confidence?: number | null;
  image_url?: string | null;
  verification?: VerificationResponse | null;
  created_at: string;
}

/** Human-readable labels for the exclusion reasons shown on the review step. */
export const NOISE_REASON_LABELS: Record<string, string> = {
  social_cta: 'Follow / share prompt',
  byline: 'Reporter byline',
  credit: 'Photo or source credit',
  timestamp: 'Date or timestamp',
  engagement: 'Like / share counter',
  copyright: 'Copyright notice',
  advert: 'Advertisement label',
  source_banner: 'Outlet name banner',
  url: 'Web address',
  social_handle: 'Social handle or hashtag',
  phone_number: 'Phone number',
  not_bangla: 'Not Bangla text',
  too_short: 'Too short to be a claim',
  low_confidence: 'Read with low confidence',
  no_letters: 'No readable letters',
  empty: 'Empty line',
};
