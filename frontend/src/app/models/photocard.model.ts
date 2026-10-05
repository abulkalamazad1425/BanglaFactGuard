// ============================================================
// Photo Card Verification Models — synced with backend
// app/features/photocard/schemas.py
//
// Image + claimed source (+ optional claimed date) in. On the server Gemini
// reads the headline, date and source from the original image (at most 3
// attempts); only if every attempt fails, EasyOCR + the deterministic
// extractor run. Only the headline is verified; the date/source read from
// the card are shown for reference and never compared with anything.
// ============================================================

import { ClaimScope, ProcessingPhase, SubmissionStatus, VerificationResponse } from './verification.model';

/** 'GEMINI_IMAGE' (primary) | 'OCR_FALLBACK' (EasyOCR + fallback extractor). */
export type ExtractionMethod = 'GEMINI_IMAGE' | 'OCR_FALLBACK';

/** HTTP 202 from POST /photocard/verify/async. The card is stored and the job is
 *  durable: extraction and verification continue on the server whether or not
 *  the browser stays open. */
export interface PhotoCardAccepted {
  submission_id: string;
  status: SubmissionStatus;
  phase?: ProcessingPhase | null;
  message: string;
  queued_at: string;
}

/** POST /photocard/verify/async — multipart form. */
export interface PhotoCardVerifyRequest {
  image: File;
  claimed_source_text: string;
  published_date?: string | null; // YYYY-MM-DD
  force_refresh?: boolean;
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
  /** The extracted headline exactly as read — the only text verified. */
  headline?: string | null;
  /** The outlet the user selected — the verification target. */
  claimed_source_text?: string | null;
  /** The date the user supplied — the only date compared with the source. */
  published_date?: string | null;

  extraction_method?: ExtractionMethod | null;
  /** Gemini attempts made (first request included, at most 3). */
  extraction_attempts?: number | null;
  fallback_used?: boolean;
  extraction_model_version?: string | null;
  extraction_failures?: string[];
  extraction_warnings: string[];
  /** Date printed on the card, raw. Display only; null when the card shows none. */
  extracted_date_text?: string | null;
  /** Outlet name printed on the card, raw. Display only; null when none is visible. */
  extracted_source_text?: string | null;

  /** EasyOCR text (fallback path only). */
  ocr_raw_text?: string | null;
  ocr_engine?: string | null;
  ocr_confidence?: number | null;
  image_url?: string | null;

  verification?: VerificationResponse | null;
  created_at: string;
}
