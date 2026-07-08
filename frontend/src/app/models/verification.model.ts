// ============================================================
// Verification Models — synced with backend schemas.py
// ============================================================

export type VerificationLabel =
  | 'TRUE'
  | 'FALSE'
  | 'PARTIALLY_TRUE'
  | 'NOT_FOUND_IN_CLAIMED_SOURCE';

export type ClaimStatus = 'PENDING' | 'PROCESSING' | 'COMPLETED' | 'FAILED';

// ── Request ──────────────────────────────────────────────────────────
export interface VerificationRequest {
  headline: string;
  claimed_source: string;
  news_body?: string | null;
  published_date?: string | null;  // YYYY-MM-DD
  force_refresh?: boolean;
}

// ── Sub-types returned in VerificationResponse ───────────────────────
export interface VerificationScores {
  semantic_similarity?: number | null;
  entity_match?: number | null;
  keyword_overlap?: number | null;
  numerical_consistency?: number | null;
  contradiction_score?: number | null;
  headline_similarity?: number | null;
  body_similarity?: number | null;
}

export interface ManipulationFlags {
  headline_manipulated?: boolean;
  body_altered?: boolean;
  numbers_altered?: boolean;
  entities_replaced?: boolean;
}

export interface MatchedArticle {
  title?: string | null;
  url: string;
  author?: string | null;
  published_date?: string | null;
  body?: string | null;
  rank_score?: number | null;
}

// ── Full response from POST /verify or GET /verify/{id} ─────────────
export interface VerificationResponse {
  claim_id: string;
  label: VerificationLabel;
  confidence: number;
  reasoning: string;
  matched_articles: MatchedArticle[];
  scores: VerificationScores;
  manipulation_flags: ManipulationFlags;
  normalized_source?: string | null;
  cached: boolean;
  processing_time_ms?: number | null;
  created_at: string;
}

// ── Submission history item from GET /users/me/submissions ───────────
export interface SubmissionSummary {
  claim_id: string;
  headline: string;
  claimed_source: string;
  status: string;
  ai_label: VerificationLabel | null;
  ai_confidence: number | null;
  submitted_at: string;
}

// ── Stats from GET /users/me/submissions/stats ───────────────────────
export interface SubmissionStats {
  total: number;
  finalized_true: number;
  finalized_false: number;
  finalized_partially_true: number;
  pending: number;
}

// ── Multimodal prediction from POST /multimodal/predict ─────────────
export interface MultimodalPredictionResult {
  prediction_id: string;
  prediction: string;          // 'FAKE' | 'NON_FAKE'
  confidence_fake: number;
  confidence_real: number;
  is_cached: boolean;
  original_id?: string | null;
  similarity_scores?: Record<string, number> | null;
  minio_object_key: string;
  model_version: string;
  created_at: string;
  processing_time_ms?: number | null;
}

// ── Old evidence/check types kept for backward compat ────────────────
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

// Kept for verify-result component compatibility
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
