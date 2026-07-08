// ============================================================
// Admin Models — synced with backend admin/schemas.py
// ============================================================

// ── Expert account response from GET /admin/experts ──────────────────
export interface ExpertResponse {
  id: string;
  email: string;
  full_name: string | null;
  is_active: boolean;
  is_verified: boolean;
  role: string;
  expertise_area?: string | null;
  credibility_score?: number | null;
  total_votes?: number | null;
  correct_votes?: number | null;
  created_at: string;
}

// ── Verdict breakdown sub-object in AdminStats ───────────────────────
export interface VerdictBreakdown {
  true_count: number;
  false_count: number;
  partially_true_count: number;
  not_found_count: number;
}

// ── Platform-wide admin stats from GET /admin/stats ─────────────────
export interface AdminStats {
  total_submissions: number;
  submissions_last_30_days: number;
  total_experts: number;
  active_experts: number;
  pending_expert_reviews: number;
  verdict_breakdown: VerdictBreakdown;
}


// ── Request to POST /admin/experts ───────────────────────────────────
export interface CreateExpertRequest {
  email: string;
  password: string;
  full_name?: string | null;
}

// ── Request to PUT /admin/experts/{id} ───────────────────────────────
export interface UpdateExpertRequest {
  full_name?: string | null;
  email?: string | null;
  is_active?: boolean;
}

// ── Request to POST /admin/experts/{id}/reset-password ──────────────
export interface ResetExpertPasswordRequest {
  new_password: string;
}

// ── Public dashboard stats from GET /dashboard/stats ─────────────────
// (used by home component; also available in admin context)
export interface PublicStats {
  total_submissions: number;
  true_count: number;
  false_count: number;
  partially_true_count: number;
  pending_count: number;
  not_found_count: number;
}

// ── Top claimed source from GET /dashboard/top-sources ───────────────
export interface TopSource {
  source: string;
  count: number;
}

