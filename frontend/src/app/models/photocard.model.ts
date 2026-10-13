import {
  ClaimScope,
  ProcessingPhase,
  SubmissionStatus,
  VerificationResponse,
} from './verification.model';

export type ExtractionStatus =
  'PENDING' | 'SUCCEEDED' | 'API_FAILED' | 'INVALID_CONTENT' | 'FAILED';

export interface PhotoCardAccepted {
  submission_id: string;
  status: SubmissionStatus;
  phase?: ProcessingPhase | null;
  message: string;
  queued_at: string;
}

export interface PhotoCardVerifyRequest {
  image: File;
}

export interface PhotoCardResultResponse {
  submission_id: string;
  status: SubmissionStatus;
  phase?: ProcessingPhase | null;
  failure_reason?: string | null;
  claim_scope?: ClaimScope;
  headline?: string | null;
  claimed_source_text?: string | null;
  claimed_source_name?: string | null;
  detected_source_text?: string | null;
  published_date?: string | null;

  extraction_status?: ExtractionStatus | null;
  extraction_attempts?: number | null;
  extraction_model_version?: string | null;
  extraction_failures?: string[];
  image_url?: string | null;

  verification?: VerificationResponse | null;
  created_at: string;
}
