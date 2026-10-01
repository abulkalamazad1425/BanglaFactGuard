// ============================================================
// Verification Models — synced with backend schemas.py
// ============================================================

// ── 3-dimensional verdict ────────────────────────────────────────────
// Source, content and date are checked independently: a date mismatch
// never implies false content, and content is only evaluated once the
// source is CONFIRMED.
export type SourceStatus = 'CONFIRMED' | 'NOT_FOUND';
export type ContentStatus = 'MATCHED' | 'ALTERED';
export type DateStatus = 'MATCHED' | 'MISMATCHED';

// ── Overall verdict — voted on by experts for EVERY submission type
// (source-based, photo card, and multimodal alike), independently of the
// (Source, Content, Date) structured vote that additionally exists for
// source-based/photo-card claims.
export type OverallVerdict = 'FAKE' | 'REAL' | 'MISLEADING' | 'ALTERED';

export type SubmissionStatus = 'PENDING' | 'PROCESSING' | 'EXPERT_REVIEW' | 'FINALIZED' | 'FAILED';

export type SubmissionType = 'SOURCE_BASED' | 'MULTIMODAL' | 'PHOTO_CARD';

// ── Request ──────────────────────────────────────────────────────────
export interface VerificationRequest {
  headline: string;
  claimed_source_text: string;
  body_text?: string | null;
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

// ── Acknowledgement from POST /verify/async ─────────────────────────
export interface VerificationQueued {
  submission_id: string;
  status: SubmissionStatus;
  /** True when this exact claim was already verified and the stored
   *  result is being reused instead of re-running the pipeline. */
  cached: boolean;
}

// ── Response from GET /verify/{id}/status ───────────────────────────
export interface VerificationStatus {
  submission_id: string;
  status: SubmissionStatus;
  result?: VerificationResponse | null;
  error?: string | null;
  queued_at: string;
  updated_at: string;
}

// ── Full response from POST /verify or GET /verify/{id} ─────────────
export interface VerificationResponse {
  submission_id: string;
  source_status: SourceStatus;
  content_status?: ContentStatus | null;
  date_status?: DateStatus | null;
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
  submission_id: string;
  headline: string;
  claimed_source_text: string;
  status: string;
  source_status: SourceStatus | null;
  content_status: ContentStatus | null;
  ai_confidence: number | null;
  submitted_at: string;
}

// ── Stats from GET /users/me/submissions/stats ───────────────────────
export interface SubmissionStats {
  total: number;
  source_confirmed: number;
  source_not_found: number;
  content_matched: number;
  content_altered: number;
  pending: number;
}

// ── Multimodal prediction from POST /multimodal/predict ─────────────
export interface MultimodalPredictionResult {
  prediction_id: string;
  submission_id: string;
  prediction: string;          // 'FAKE' | 'NON_FAKE' — the AI's preliminary call
  confidence_fake: number;
  confidence_real: number;
  /** NULL until expert review finalizes this claim — see SubmissionLookup.status. */
  expert_overall_verdict?: OverallVerdict | null;
  is_cached: boolean;
  original_id?: string | null;
  similarity_scores?: Record<string, number> | null;
  minio_object_key: string;
  image_url?: string | null;
  model_version: string;
  created_at: string;
  processing_time_ms?: number | null;
}

// ── Multimodal prediction from GET /multimodal/predict/{id} or
//    GET /multimodal/by-submission/{submission_id} — includes the original
//    claim text, which the bare prediction response above does not. ────
export interface MultimodalPredictionDetail {
  prediction_id: string;
  submission_id: string;
  headline: string | null;
  body_text: string | null;
  prediction: string;          // 'FAKE' | 'NON_FAKE' — the AI's preliminary call
  confidence_fake: number;
  confidence_real: number;
  expert_overall_verdict?: OverallVerdict | null;
  is_cached: boolean;
  original_id?: string | null;
  minio_object_key: string;
  image_url?: string | null;
  model_version: string;
  created_at: string;
  updated_at: string;
}

// ── Type-agnostic lookup from GET /submissions/{id} ──────────────────
// The first call a result page makes: tells it which detail endpoint to
// call next (GET /verify/{id}, GET /multimodal/by-submission/{id}, or
// GET /photocard/{id}) and carries enough to render a loading/pending
// state before that second call resolves.
export interface SubmissionLookup {
  submission_id: string;
  submission_type: SubmissionType;
  status: SubmissionStatus;
  headline: string | null;
  claimed_source_text?: string | null;
  published_date?: string | null;
  created_at: string;
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
  submission_id: string;
  source_status: SourceStatus;
  content_status?: ContentStatus | null;
  date_status?: DateStatus | null;
  confidence: number;
  explanation?: string;
  evidence_articles?: EvidenceArticle[];
  checks?: VerificationCheck[];
  processing_time_ms?: number;
  created_at?: string;
  status?: SubmissionStatus;
}
