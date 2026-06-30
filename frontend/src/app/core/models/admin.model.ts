// ============================================================
// Admin & Dashboard Models
// ============================================================

export interface ExpertResponse {
  id: string;
  full_name: string | null;
  email: string;
  role: string;
  is_active: boolean;
  expertise_area: string | null;
  credibility_score: number | null;
  total_votes: number;
}

export interface CreateExpertRequest {
  full_name: string;
  email: string;
  password: string;
  expertise_area: string;
}

export interface UpdateExpertRequest {
  full_name?: string;
  email?: string;
  expertise_area?: string;
  is_active?: boolean;
}

export interface VerdictBreakdown {
  true_count: number;
  false_count: number;
  partially_true_count: number;
  not_found_count: number;
}

export interface AdminStats {
  total_submissions: number;
  submissions_last_30_days: number;
  verdict_breakdown: VerdictBreakdown;
  pending_expert_reviews: number;
  total_experts: number;
  active_experts: number;
  avg_verification_time_seconds: number | null;
}

// Public dashboard
export interface PublicStats {
  total_submissions: number;
  true_count: number;
  false_count: number;
  partially_true_count: number;
  not_found_count: number;
  pending_count: number;
}

export interface TopSource {
  source: string;
  count: number;
}
