// ============================================================
// Expert Models — synced with backend expert_review/schemas.py
// ============================================================

export type ExpertLabel = 'TRUE' | 'FALSE' | 'PARTIALLY_TRUE' | 'NOT_FOUND_IN_CLAIMED_SOURCE';

// ── Queue item from GET /expert/queue ────────────────────────────────
export interface ExpertQueueItem {
  claim_id: string;
  headline: string;
  claimed_source: string;
  normalized_source?: string | null;
  ai_label?: string | null;
  ai_confidence?: number | null;
  submitted_at: string;
  has_voted: boolean;
  vote_count: number;
}

// ── Review detail from GET /expert/queue/{claim_id} ─────────────────
export interface ExpertReviewDetail {
  claim_id: string;
  headline: string;
  claimed_source: string;
  news_body?: string | null;
  ai_label?: string | null;
  ai_confidence?: number | null;
  reasoning?: string | null;
}

// ── Submitted vote response ──────────────────────────────────────────
export interface ExpertReviewResponse {
  review_id: string;
  claim_id: string;
  expert_id: string;
  expert_label: ExpertLabel;
  justification?: string | null;
  created_at: string;
}

// ── History item from GET /expert/history ───────────────────────────
export interface ExpertHistoryItem {
  review_id: string;
  claim_id: string;
  headline: string;
  claimed_source: string;
  expert_label: ExpertLabel;
  justification?: string | null;
  final_label?: string | null;
  is_correct?: boolean | null;
  matched?: boolean | null;
  voted_at?: string | null;
  ai_label?: string | null;
  reviewed_at: string;
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

// ── Request to POST /expert/queue/{claim_id}/vote ───────────────────
export interface ExpertVoteRequest {
  expert_label: ExpertLabel;
  justification?: string | null;
}

// ── Request to PUT /expert/reviews/{review_id} ──────────────────────
export interface ExpertVoteUpdateRequest {
  expert_label: ExpertLabel;
  justification?: string | null;
}
