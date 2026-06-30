// ============================================================
// Verification Models
// ============================================================

export type VerificationLabel =
  | 'TRUE'
  | 'FALSE'
  | 'PARTIALLY_TRUE'
  | 'NOT_FOUND_IN_CLAIMED_SOURCE';

export type ClaimStatus = 'PENDING' | 'PROCESSING' | 'COMPLETED' | 'FAILED';

export interface VerificationRequest {
  headline: string;
  body?: string;
  claimed_source: string;
}

export interface EvidenceArticle {
  title: string;
  url: string;
  source: string;
  semantic_similarity?: number;
  nli_score?: number;
  published_at?: string;
}

export interface VerificationCheck {
  stage: string;
  passed: boolean;
  detail?: string;
}

export interface VerificationResult {
  claim_id: string;
  label: VerificationLabel;
  confidence: number;
  explanation?: string;
  evidence_articles?: EvidenceArticle[];
  checks?: VerificationCheck[];
  processing_time_ms?: number;
  created_at?: string;
  status?: ClaimStatus;
}

export interface SubmissionSummary {
  claim_id: string;
  headline: string;
  claimed_source: string;
  status: string;
  ai_label: VerificationLabel | null;
  ai_confidence: number | null;
  submitted_at: string;
}

export interface SubmissionStats {
  total: number;
  finalized_true: number;
  finalized_false: number;
  finalized_partially_true: number;
  pending: number;
}

export interface MultimodalPredictionRequest {
  text: string;
}

export interface MultimodalPredictionResult {
  prediction_id: string;
  label: string;
  confidence: number;
  processing_time_ms?: number;
  image_url?: string;
}
