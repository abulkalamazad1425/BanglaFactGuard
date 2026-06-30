// ============================================================
// Expert Review Models
// ============================================================

import { VerificationLabel } from './verification.model';

export interface ExpertQueueItem {
  claim_id: string;
  headline: string;
  claimed_source: string;
  ai_label: VerificationLabel | null;
  ai_confidence: number | null;
  submitted_at: string;
  vote_count: number;
}

export interface ExpertVoteRequest {
  expert_label: VerificationLabel;
  justification: string;
}

export interface ExpertReviewResponse {
  id: string;
  claim_id: string;
  reviewer_id: string | null;
  ai_label: string;
  expert_label: string;
  justification: string;
  credibility_weight: number;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface ExpertHistoryItem {
  review_id: string;
  claim_id: string;
  headline: string | null;
  claimed_source: string | null;
  expert_label: string;
  ai_label: string;
  final_label: string | null;
  matched: boolean | null;
  voted_at: string;
}

export interface ExpertStats {
  user_id: string;
  full_name: string | null;
  total_votes: number;
  correct_votes: number;
  accuracy_pct: number | null;
  current_credibility: number;
}
