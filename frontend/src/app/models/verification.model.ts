// ============================================================
// Verification Models — synced with backend schemas.py
// ============================================================

// ── 3-dimensional verdict ────────────────────────────────────────────
// Source, content and date are checked independently: a date mismatch
// never implies false content, and content is only evaluated once the
// source is CONFIRMED.
// INCOMPLETE means the check itself could not be completed (search/retrieval/
// extraction failure, or the source's own publication date was undeterminable)
// — distinct from a completed check that found a negative result (NOT_FOUND,
// MISMATCHED). A failed check must never be displayed as a confident negative.
export type SourceStatus = 'CONFIRMED' | 'NOT_FOUND' | 'INCOMPLETE';
export type ContentStatus = 'MATCHED' | 'ALTERED' | 'INCOMPLETE';
export type DateStatus = 'MATCHED' | 'MISMATCHED' | 'INCOMPLETE';

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

/** Outcome of one alteration check. PASSED is the only state that may be shown
 *  as a green check; NOT_EVALUATED (could not run) and NOT_APPLICABLE are not passes. */
export type CheckState = 'PASSED' | 'FAILED' | 'NOT_EVALUATED' | 'NOT_APPLICABLE';

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
/** Measurements, not probabilities of truth. null = no measurement; the reason
 *  is in `analysis.metrics[name].state` - never render null as 0% or 100%. */
export interface VerificationScores {
  semantic_similarity?: number | null;
  entity_match?: number | null;
  keyword_overlap?: number | null;
  numerical_consistency?: number | null;
  contradiction_score?: number | null;
  headline_similarity?: number | null;
  /** Submitted body vs source passages. null for HEADLINE_ONLY (always for photo cards). */
  body_similarity?: number | null;
  passage_similarity?: number | null;
  headline_keyword_coverage?: number | null;
  passage_keyword_coverage?: number | null;
  body_keyword_coverage?: number | null;
}

export interface MetricDetail {
  state: MetricState;
  value?: number | null;
  reason?: string | null;
  details?: Record<string, unknown>;
}

export interface EvidencePassage {
  text: string;
  score: number;
  location: string;
  first_sentence?: number | null;
  last_sentence?: number | null;
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

export interface NLIAnalysis {
  entailment?: number | null;
  neutral?: number | null;
  contradiction?: number | null;
  premise?: string | null;
  reliability?: string;
}

export interface AnalysisDetails {
  pipeline_version?: string | null;
  claim_scope?: ClaimScope | null;
  metrics: Record<string, MetricDetail>;
  passages: EvidencePassage[];
  nli?: NLIAnalysis | null;
  search?: SearchAccounting | null;
  date?: DateAnalysis | null;
  source_basis: string[];
  content_basis: string[];
  stage_errors?: Record<string, string>;
}

export interface DiscrepancyDetail {
  kind: string;
  claim_text: string;
  evidence_text?: string | null;
  detail: string;
  part: 'headline' | 'body' | string;
}

export interface AlteredNumberDetail {
  claimed: string;
  nearest_in_article?: string | null;
}

export interface SubstitutedEntityDetail {
  entity_type: string;
  claimed: string[];
  article_same_type: string[];
}

/** A boolean is true ONLY when a concrete discrepancy was found; false does NOT
 *  mean "verified". Read `check_states`; an empty map (historical rows) means
 *  the checks were not evaluated. */
export interface ManipulationFlags {
  headline_manipulated?: boolean;
  body_altered?: boolean;
  numbers_altered?: boolean;
  entities_replaced?: boolean;
  altered_numbers?: AlteredNumberDetail[];
  substituted_entities?: SubstitutedEntityDetail[];
  check_states?: Record<string, CheckState>;
  discrepancies?: DiscrepancyDetail[];
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
  claim_scope?: ClaimScope | null;
  /** What `confidence` means: a measurement summary, not a probability of truth. */
  confidence_meaning?: string;
  pipeline_version?: string | null;
  analysis?: AnalysisDetails | null;
}

// ── Submission history item from GET /users/me/submissions ───────────
export interface SubmissionSummary {
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
