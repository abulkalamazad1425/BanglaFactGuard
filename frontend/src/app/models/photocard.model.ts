// ============================================================
// Photo Card Verification Models — synced with backend
// app/features/photocard/schemas.py
//
// Fully unattended, single pass: image + claimed source + published date in,
// a verdict out. No extraction-preview/confirmation step.
// ============================================================

import { ClaimScope, ProcessingPhase, SubmissionStatus, VerificationResponse } from './verification.model';

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

/** HTTP 202 from POST /photocard/verify/async. The card is stored and the job is
 *  durable: OCR, extraction and verification continue on the server whether or
 *  not the browser stays open. */
export interface PhotoCardAccepted {
  submission_id: string;
  status: SubmissionStatus;
  phase?: ProcessingPhase | null;
  message: string;
  queued_at: string;
}

/** POST /photocard/verify/async (or the synchronous /photocard/verify) — multipart form. */
export interface PhotoCardVerifyRequest {
  image: File;
  claimed_source_text: string;
  published_date?: string | null; // YYYY-MM-DD
  force_refresh?: boolean;
}

export interface PhotoCardVerifyResponse {
  submission_id: string;
  verification: VerificationResponse;

  extracted_headline: string;
  /** 'GEMINI' | 'EXISTING_FALLBACK' — which extractor produced it. */
  extractor_used: string;
  extraction_model_version?: string | null;
  extraction_warnings: string[];

  detected_sources: DetectedSource[];
  detected_source_text?: string | null;
  detected_date_text?: string | null;
  /** Legacy API name: only detected-source disagreement; extracted dates are never compared. */
  source_date_conflict: boolean;

  ocr_raw_text: string;
  ocr_engine: string;
  ocr_confidence?: number | null;
  image_url?: string | null;

  claimed_source_text: string;
  published_date?: string | null;

  reused_previous_result: boolean;
  original_submission_id?: string | null;
}

/** GET /photocard/{submission_id} — a stored report. */
export interface PhotoCardResultResponse {
  submission_id: string;
  status: SubmissionStatus;
  phase?: ProcessingPhase | null;
  /** User-presentable reason when status is FAILED. */
  failure_reason?: string | null;
  /** Always HEADLINE_ONLY for photo cards. */
  claim_scope?: ClaimScope;
  headline?: string | null;
  claimed_source_text?: string | null;
  published_date?: string | null;

  ocr_raw_text?: string | null;
  ocr_engine?: string | null;
  ocr_confidence?: number | null;
  image_url?: string | null;

  extractor_used?: string | null;
  extraction_model_version?: string | null;
  extraction_warnings: string[];
  detected_source_text?: string | null;
  detected_date_text?: string | null;
  source_date_conflict?: boolean;

  verification?: VerificationResponse | null;
  created_at: string;
}
