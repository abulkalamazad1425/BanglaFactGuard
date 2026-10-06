// ============================================================
// Expert Models — synced with backend expert_review/schemas.py
// ============================================================

import {
  BodySimilarityReport,
  ContentStatus,
  DateStatus,
  HeadlineAlterationDetail,
  HeadlineAlterationStatus,
  HeadlineCheckStatus,
  OverallVerdict,
  SourceStatus,
  SubmissionStatus,
  SubmissionType,
} from './verification.model';

// ── Queue item from GET /expert/queue ────────────────────────────────
export interface ExpertTopArticle {
  url: string;
  title?: string | null;
  published_date?: string | null;
  rank_score?: number | null;
  body_snippet?: string | null;
}

export interface ExpertQueueItem {
  submission_id: string;
  submission_type: SubmissionType;
  status?: SubmissionStatus | null;
  escalated_at?: string | null;
  published_date?: string | null;
  /** Whether the requesting reviewer may vote now (admins: escalated claims only). */
  can_vote?: boolean;
  /** ADMIN_FINAL when an admin's vote will be the final decision. */
  decision_mode?: 'EXPERT_VOTE' | 'ADMIN_FINAL';
  headline: string;
  body_text?: string | null;
  claimed_source_text: string;
  normalized_source?: string | null;
  ai_label?: string | null;
  ai_overall_verdict?: OverallVerdict | null;
  source_status?: SourceStatus | null;
  content_status?: ContentStatus | null;
  headline_status?: HeadlineAlterationStatus | null;
  date_status?: DateStatus | null;
  ai_confidence?: number | null;
  submitted_at: string;
  has_voted: boolean;
  vote_count: number;
  top_article?: ExpertTopArticle | null;
  /** Multimodal submissions only — the submitted card/photo. */
  image_url?: string | null;
  /** Why content_status (the headline verdict) may be null. */
  headline_check_status?: HeadlineCheckStatus | null;
  /** Headline Alteration detail (claim headline vs. source title only). */
  headline_alteration?: HeadlineAlterationDetail | null;
  /** Claim body vs. source body similarity measurements — never a verdict. */
  body_similarity?: BodySimilarityReport | null;
}

// ── Review detail from GET /expert/queue/{submission_id} ────────────
export interface ExpertReviewDetail {
  submission_id: string;
  headline: string;
  claimed_source_text: string;
  body_text?: string | null;
  ai_label?: string | null;
  source_status?: SourceStatus | null;
  content_status?: ContentStatus | null;
  date_status?: DateStatus | null;
  ai_confidence?: number | null;
  reasoning?: string | null;
}

// ── Submitted vote response — matches backend ExpertReviewResponse ──
export interface ExpertReviewResponse {
  id: string;
  submission_id: string;
  reviewer_id: string | null;
  ai_overall_verdict: OverallVerdict;
  ai_source_status: SourceStatus | null;
  ai_content_status: ContentStatus | null;
  ai_date_status: DateStatus | null;
  vote_overall_verdict: OverallVerdict;
  vote_source_status: SourceStatus | null;
  vote_content_status: ContentStatus | null;
  vote_date_status: DateStatus | null;
  justification?: string | null;
  credibility_weight: number;
  status: string;
  is_admin_decision?: boolean;
  created_at: string;
  updated_at: string;
}

// ── History item from GET /expert/history ───────────────────────────
export interface ExpertHistoryItem {
  review_id: string;
  submission_id: string;
  submission_type: SubmissionType;
  headline: string;
  claimed_source_text: string;
  vote_overall_verdict: OverallVerdict;
  vote_source_status: SourceStatus | null;
  vote_content_status: ContentStatus | null;
  vote_date_status: DateStatus | null;
  ai_overall_verdict: OverallVerdict;
  ai_source_status: SourceStatus | null;
  ai_content_status: ContentStatus | null;
  ai_date_status: DateStatus | null;
  final_overall_verdict?: OverallVerdict | null;
  final_source_status?: SourceStatus | null;
  final_content_status?: ContentStatus | null;
  final_date_status?: DateStatus | null;
  matched?: boolean | null;
  submission_status?: SubmissionStatus | null;
  is_admin_decision?: boolean;
  voted_at: string;
}

// ── Stats from GET /expert/stats ─────────────────────────────────────
export interface ExpertStats {
  total_reviews: number;
  correct_reviews: number;
  accuracy_rate: number;
  pending_reviews: number;
  // Additional fields used by expert-stats component
  total_votes?: number;
  correct_votes?: number;
  accuracy_pct?: number | null;
  current_credibility: number | null;
  activation_threshold?: number;
}

// ── Credibility from GET /expert/credibility ─────────────────────────
export interface CredibilityScore {
  user_id: string;
  score: number | null;
  total_votes: number;
  correct_votes: number;
  updated_at: string;
}

// ── Request to POST /expert/queue/{submission_id}/vote ──────────────
// overall_verdict is required for every submission type. source_status
// (plus, conditionally, content_status/date_status) additionally applies to
// SOURCE_BASED/PHOTO_CARD claims only — omit all three for MULTIMODAL.
export interface ExpertVoteRequest {
  overall_verdict: OverallVerdict;
  source_status?: SourceStatus | null;
  content_status?: ContentStatus | null;
  date_status?: DateStatus | null;
  justification: string;
}

// ── Request to PUT /expert/reviews/{review_id} ──────────────────────
export interface ExpertVoteUpdateRequest {
  overall_verdict?: OverallVerdict | null;
  source_status?: SourceStatus | null;
  content_status?: ContentStatus | null;
  date_status?: DateStatus | null;
  justification?: string | null;
}
