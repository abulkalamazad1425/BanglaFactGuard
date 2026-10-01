// ============================================================
// Expert Models — synced with backend expert_review/schemas.py
// ============================================================

import { ContentStatus, DateStatus, OverallVerdict, SourceStatus, SubmissionType } from './verification.model';

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
  headline: string;
  body_text?: string | null;
  claimed_source_text: string;
  normalized_source?: string | null;
  ai_label?: string | null;
  ai_overall_verdict?: OverallVerdict | null;
  source_status?: SourceStatus | null;
  content_status?: ContentStatus | null;
  date_status?: DateStatus | null;
  ai_confidence?: number | null;
  submitted_at: string;
  has_voted: boolean;
  vote_count: number;
  top_article?: ExpertTopArticle | null;
  /** Multimodal submissions only — the submitted card/photo. */
  image_url?: string | null;
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
  current_credibility: number;
}

// ── Credibility from GET /expert/credibility ─────────────────────────
export interface CredibilityScore {
  user_id: string;
  score: number;
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
