export type SourceStatus = 'CONFIRMED' | 'NOT_FOUND' | 'INCOMPLETE';
export type ContentStatus = 'MATCHED' | 'ALTERED';
export type DateStatus = 'MATCHED' | 'MISMATCHED' | 'INCOMPLETE';
export type HeadlineAlterationStatus = 'EXACT_MATCHED' | 'MEANING_PRESERVED' | 'ALTERED';
export type HeadlineCheckStatus =
  | 'COMPLETED'
  | 'SOURCE_NOT_FOUND'
  | 'SOURCE_CHECK_INCOMPLETE'
  | 'SOURCE_TITLE_MISSING'
  | 'MODEL_UNAVAILABLE'
  | 'UNDETERMINED';
export type BodyComparisonStatus = 'COMPUTED' | 'SKIPPED' | 'UNAVAILABLE';

export type OverallVerdict = 'FAKE' | 'REAL' | 'MISLEADING' | 'ALTERED';

export type SubmissionStatus =
  'PENDING' | 'PROCESSING' | 'EXPERT_REVIEW' | 'FINALIZED' | 'FAILED' | 'ESCALATED';

export type SubmissionType = 'SOURCE_BASED' | 'MULTIMODAL' | 'PHOTO_CARD';

export type ClaimScope = 'HEADLINE_ONLY' | 'HEADLINE_WITH_BODY';

export type MetricState = 'COMPUTED' | 'NOT_APPLICABLE' | 'EMPTY' | 'UNAVAILABLE';

export type ProcessingPhase = 'QUEUED' | 'EXTRACTING' | 'VERIFYING' | 'DONE' | 'FAILED';

export interface VerificationRequest {
  headline: string;
  claimed_source_text?: string | null;
  body_text?: string | null;
  published_date?: string | null;
}

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
  article_date?: string | null;
  article_published_at?: string | null;
  provenance?: string | null;
  tz_assumed?: boolean;
  timezone?: string;
}

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
  embedding_cosine?: number | null;
  reason?: string | null;
}

export interface HeadlineAlterationDetail {
  status: HeadlineCheckStatus;
  verdict?: ContentStatus | null;
  reason: string;
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

export interface BodySimilarityMetric {
  available: boolean;
  value?: number | null;
  raw_value?: number | null;
  reason?: string | null;
  details?: Record<string, unknown>;
}

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
  metrics?: Record<string, MetricDetail>;
  search?: SearchAccounting | null;
  source_basis?: string[];
  headline_alteration?: HeadlineAlterationDetail | null;
  body_similarity?: BodySimilarityReport | null;
  date?: DateAnalysis | null;
  stage_errors?: Record<string, string>;
  source_scope?: SourceScopeDetails | null;
}

export type VerificationMode = 'CLAIMED_SOURCE' | 'VERIFIED_SOURCES';

export interface SourceScopeDetails {
  verification_mode: VerificationMode;
  resolution_reason?: string | null;
  raw_source_text?: string | null;
  claimed_source?: string | null;
  eligible_publishers?: string[];
  evidence_publishers?: string[];
  primary_article_url?: string | null;
  primary_publisher?: string | null;
  incomplete_reason?: string | null;
}

export interface MatchedArticle {
  title?: string | null;
  url: string;
  author?: string | null;
  published_date?: string | null;
  body?: string | null;
  rank_score?: number | null;
  publisher?: string | null;
  is_primary?: boolean;
}

export interface VerificationQueued {
  submission_id: string;
  status: SubmissionStatus;
  cached: boolean;
}

export interface VerificationStatus {
  submission_id: string;
  status: SubmissionStatus;
  phase?: ProcessingPhase | null;
  result?: VerificationResponse | null;
  error?: string | null;
  queued_at: string;
  updated_at: string;
}

export interface VerificationResponse {
  submission_id: string;
  overall_verdict?: OverallVerdict | null;
  is_finalized?: boolean;
  review_pending?: boolean;
  decided_by_admin?: boolean;
  was_overridden?: boolean;
  ai_source_status?: SourceStatus | null;
  ai_content_status?: ContentStatus | null;
  ai_date_status?: DateStatus | null;
  source_status: SourceStatus;
  content_status?: ContentStatus | null;
  headline_status?: HeadlineAlterationStatus | null;
  headline_check_status?: HeadlineCheckStatus | null;
  date_status?: DateStatus | null;
  claimed_published_date?: string | null;
  confidence: number;
  reasoning: string;
  matched_articles: MatchedArticle[];
  normalized_source?: string | null;
  verification_mode?: VerificationMode;
  source_resolution_reason?: string | null;
  cached: boolean;
  processing_time_ms?: number | null;
  created_at: string;
  claim_scope?: ClaimScope | null;
  confidence_meaning?: string;
  pipeline_version?: string | null;
  legacy_result?: boolean;
  analysis?: AnalysisDetails | null;
}

export type MySubmissionState = 'in_progress' | 'review' | 'final' | 'failed';
export interface MySubmissionFilters {
  q?: string;
  state?: MySubmissionState | '';
  type?: SubmissionType | '';
}

export interface SubmissionSummary {
  prediction?: string | null;
  submission_id: string;
  submission_type: SubmissionType;
  headline: string | null;
  claimed_source_text: string | null;
  status: string;
  phase?: ProcessingPhase | null;
  failure_reason?: string | null;
  source_status: SourceStatus | null;
  content_status: ContentStatus | null;
  headline_status?: HeadlineAlterationStatus | null;
  date_status?: DateStatus | null;
  published_date?: string | null;
  overall_verdict?: OverallVerdict | null;
  is_finalized?: boolean;
  ai_confidence: number | null;
  image_url?: string | null;
  submitted_at: string;
  updated_at?: string | null;
}

export interface SubmissionStats {
  total: number;
  source_confirmed: number;
  source_not_found: number;
  content_matched: number;
  content_altered: number;
  pending: number;
}

export interface MultimodalPredictionResult {
  prediction_id: string;
  submission_id: string;
  prediction: string;
  confidence_fake: number;
  confidence_real: number;
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

export interface MultimodalPredictionDetail {
  prediction_id: string;
  submission_id: string;
  headline: string | null;
  body_text: string | null;
  prediction: string;
  confidence_fake: number;
  confidence_real: number;
  expert_overall_verdict?: OverallVerdict | null;
  is_cached: boolean;
  original_id?: string | null;
  original_submission_id?: string | null;
  minio_object_key: string;
  image_url?: string | null;
  model_version: string;
  created_at: string;
  updated_at: string;
}

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

export interface PublicVote {
  reviewer_name: string;
  reviewer_role: 'Expert' | 'Admin';
  overall_vote: OverallVerdict;
  justification?: string | null;
  voted_at: string;
  is_final_decision: boolean;
}

export interface PublicVotingDetails {
  submission_id: string;
  final_verdict: OverallVerdict;
  decided_by: 'EXPERT_CONSENSUS' | 'ADMIN';
  finalized_at?: string | null;
  votes: PublicVote[];
}
