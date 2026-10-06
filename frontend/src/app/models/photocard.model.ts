// ============================================================
// Photo Card Verification Models — synced with backend
// app/features/photocard/schemas.py
//
// Image only in. On the server Gemini reads the headline, identifies the
// news outlet among the active verified sources (name, logo or alias) and
// reads the printed date (at most 9 requests). Those values ARE the claim:
// claimed_source_text / published_date below are what the card shows.
// ============================================================

import { ClaimScope, ProcessingPhase, SubmissionStatus, VerificationResponse } from './verification.model';

/** PENDING until read; API_FAILED: the card could not be read (temporary);
 *  INVALID_CONTENT: no headline or no recognised outlet on the card. */
export type ExtractionStatus = 'PENDING' | 'SUCCEEDED' | 'API_FAILED' | 'INVALID_CONTENT' | 'FAILED';

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

/** POST /photocard/verify/async — multipart form: the image only. */
export interface PhotoCardVerifyRequest {
  image: File;
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
  /** The headline exactly as printed on the card — the only text verified. */
  headline?: string | null;
  /** Canonical id of the verified outlet identified on the card — the claimed outlet. */
  claimed_source_text?: string | null;
  /** Display name of that outlet. */
  claimed_source_name?: string | null;
  /** Publication date printed on the card — the claimed date; null when the card shows none. */
  published_date?: string | null;

  extraction_status?: ExtractionStatus | null;
  /** Gemini requests made (first request included, at most 9). */
  extraction_attempts?: number | null;
  extraction_model_version?: string | null;
  extraction_failures?: string[];
  image_url?: string | null;

  verification?: VerificationResponse | null;
  created_at: string;
}
