// ============================================================
// Verification Models — synced with backend schemas.py
// ============================================================

// ── Independent findings ─────────────────────────────────────────────
// Source, Headline Alteration and date are decided separately: a date
// mismatch never implies an altered headline, and the headline is only
// compared once the source is CONFIRMED.
// INCOMPLETE means the check itself could not be completed (search/retrieval
// failure, or the source's own publication date was undeterminable) — never a
// confident negative such as NOT_FOUND or MISMATCHED.
export type SourceStatus = 'CONFIRMED' | 'NOT_FOUND' | 'INCOMPLETE';
/** Headline Alteration verdict: the claim headline vs the source TITLE only.
 *  There is no third verdict; when none was reached `content_status` is null
 *  and `headline_check_status` says why. */
export type ContentStatus = 'MATCHED' | 'ALTERED';
export type DateStatus = 'MATCHED' | 'MISMATCHED' | 'INCOMPLETE';
/** Processing status of the headline check — separate from the verdict. */
export type HeadlineCheckStatus =
  | 'COMPLETED'
  | 'SOURCE_NOT_FOUND'
  | 'SOURCE_CHECK_INCOMPLETE'
  | 'SOURCE_TITLE_MISSING'
  | 'MODEL_UNAVAILABLE'
  | 'UNDETERMINED';
/** Whether the claim-body vs source-body scores were computed. */
export type BodyComparisonStatus = 'COMPUTED' | 'SKIPPED' | 'UNAVAILABLE';

// ── Overall verdict — voted on by experts for EVERY submission type
// (source-based, photo card, and multimodal alike), independently of the
// (Source, Content, Date) structured vote that additionally exists for
// source-based/photo-card claims.
export type OverallVerdict = 'FAKE' | 'REAL' | 'MISLEADING' | 'ALTERED';

export type SubmissionStatus =
  | 'PENDING'
  | 'PROCESSING'
  | 'EXPERT_REVIEW'
  | 'FINALIZED'
  | 'FAILED'
  | 'ESCALATED';

export type SubmissionType = 'SOURCE_BASED' | 'MULTIMODAL' | 'PHOTO_CARD';

/** What the pipeline treated as "the claim". Photo cards are ALWAYS
 *  HEADLINE_ONLY (no submitted body exists to compare). */
export type ClaimScope = 'HEADLINE_ONLY' | 'HEADLINE_WITH_BODY';

/** Why a score is (or is not) a number. */
export type MetricState = 'COMPUTED' | 'NOT_APPLICABLE' | 'EMPTY' | 'UNAVAILABLE';

/** Progress inside PENDING/PROCESSING (public lifecycle enum is unchanged). */
export type ProcessingPhase = 'QUEUED' | 'EXTRACTING' | 'VERIFYING' | 'DONE' | 'FAILED';

// ── Request ──────────────────────────────────────────────────────────
export interface VerificationRequest {
  headline: string;
  claimed_source_text: string;
  body_text?: string | null;
  published_date?: string | null;  // YYYY-MM-DD
  force_refresh?: boolean;
}

// ── Sub-types returned in VerificationResponse ───────────────────────
/** A source-correspondence measurement. null value = no measurement (see state), never 0. */
export interface MetricDetail {
  state: MetricState;
  value?: number | null;
  reason?: string | null;
  details?: Record<string, unknown>;
}

export interface SearchAccounting {
  attempted: number;
  success: number;
  success_empty: number;
  failed: number;
  skipped: number;
  cached: number;
  adequate?: boolean | null;
  providers?: Record<string, Record<string, number>>;
  redirect_rejected?: number;
}

export interface DateAnalysis {
  claimed_date?: string | null;
  /** datePublished as a calendar day in Asia/Dhaka. */
  article_date?: string | null;
  article_published_at?: string | null;
  provenance?: string | null;
  tz_assumed?: boolean;
  timezone?: string;
}

/** One material difference between the claim headline and the source title. */
export interface HeadlineDifference {
  kind: string;
  detail: string;
  claim_text: string;
  source_text: string;
}

export interface HeadlineSemanticAssessment {
  available: boolean;
  entailment_title_to_claim?: number | null;
  contradiction_title_to_claim?: number | null;
  entailment_claim_to_title?: number | null;
  contradiction_claim_to_title?: number | null;
  /** Raw LaBSE cosine, -1..1. */
  embedding_cosine?: number | null;
  reason?: string | null;
}

/** Headline Alteration — the claim headline compared ONLY with the selected
 *  source article's title (never its body). */
export interface HeadlineAlterationDetail {
  status: HeadlineCheckStatus;
  verdict?: ContentStatus | null;
  /** Short, evidence-based basis for the verdict or for its absence. */
  reason: string;
  /** True when decided by an exact match before any alteration analysis ran. */
  exact_match: boolean;
  basis?: string;
  claim_headline: string;
  source_title?: string | null;
  source_publisher?: string | null;
  source_url?: string | null;
  differences?: HeadlineDifference[];
  semantic?: HeadlineSemanticAssessment | null;
  ner_available?: boolean;
  method?: string | null;
}

/** One body similarity measurement. `value` is the displayed 0–1 score and is
 *  null when unavailable — never a default 0. */
export interface BodySimilarityMetric {
  available: boolean;
  value?: number | null;
  raw_value?: number | null;
  reason?: string | null;
  details?: Record<string, unknown>;
}

/** Claim body vs source body — similarity MEASUREMENTS only, never a truth,
 *  alteration or contradiction verdict. */
export interface BodySimilarityReport {
  status: BodyComparisonStatus;
  reason?: string | null;
  tfidf_cosine?: BodySimilarityMetric | null;
  jaccard?: BodySimilarityMetric | null;
  normalized_levenshtein?: BodySimilarityMetric | null;
  semantic_cosine?: BodySimilarityMetric | null;
  claim_chars?: number | null;
  source_chars?: number | null;
}

export interface AnalysisDetails {
  pipeline_version?: string | null;
  claim_scope?: ClaimScope | null;
  /** Source-correspondence measurements. */
  metrics?: Record<string, MetricDetail>;
  search?: SearchAccounting | null;
  source_basis?: string[];
  headline_alteration?: HeadlineAlterationDetail | null;
  body_similarity?: BodySimilarityReport | null;
  date?: DateAnalysis | null;
  stage_errors?: Record<string, string>;
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
  phase?: ProcessingPhase | null;
  result?: VerificationResponse | null;
  error?: string | null;
  queued_at: string;
  updated_at: string;
}

// ── Full response from POST /verify or GET /verify/{id} ─────────────
export interface VerificationResponse {
  submission_id: string;
  /** The expert-finalized Overall verdict. NULL until expert review finalizes
   *  the claim - the automated system never sets it. */
  overall_verdict?: OverallVerdict | null;
  /** True once expert review has finalized overall_verdict. */
  is_finalized?: boolean;
  /** True until finalization: show "review pending", never a truth badge. */
  review_pending?: boolean;
  /** True if expert review's finalized verdict differs from the AI's original call. */
  was_overridden?: boolean;
  /** The AI's own original call — immutable, never changed by expert review. */
  ai_source_status?: SourceStatus | null;
  ai_content_status?: ContentStatus | null;
  ai_date_status?: DateStatus | null;
  source_status: SourceStatus;
  /** Headline Alteration verdict (MATCHED | ALTERED), or null. */
  content_status?: ContentStatus | null;
  headline_check_status?: HeadlineCheckStatus | null;
  date_status?: DateStatus | null;
  /** Source-correspondence strength — not a probability of truth. */
  confidence: number;
  reasoning: string;
  matched_articles: MatchedArticle[];
  normalized_source?: string | null;
  cached: boolean;
  processing_time_ms?: number | null;
  created_at: string;
  claim_scope?: ClaimScope | null;
  /** What `confidence` means: a measurement summary, not a probability of truth. */
  confidence_meaning?: string;
  pipeline_version?: string | null;
  /** Stored by the pre-Headline-Alteration pipeline: its old content verdict is not shown. */
  legacy_result?: boolean;
  analysis?: AnalysisDetails | null;
}

// ── Submission history item from GET /users/me/submissions ───────────
export interface SubmissionSummary {
  prediction?: string | null;
  submission_id: string;
  submission_type: SubmissionType;
  /** null for a just-accepted photo card (the headline is extracted in the background). */
  headline: string | null;
  claimed_source_text: string | null;
  status: string;
  phase?: ProcessingPhase | null;
  failure_reason?: string | null;
  source_status: SourceStatus | null;
  content_status: ContentStatus | null;
  date_status?: DateStatus | null;
  /** Expert-finalized only. */
  overall_verdict?: OverallVerdict | null;
  is_finalized?: boolean;
  ai_confidence: number | null;
  image_url?: string | null;
  submitted_at: string;
  updated_at?: string | null;
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
  body_text?: string | null;
  claimed_source_text?: string | null;
  published_date?: string | null;
  processing_phase?: ProcessingPhase | null;
  failure_reason?: string | null;
  created_at: string;
}
