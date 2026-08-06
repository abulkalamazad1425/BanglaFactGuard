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
  avg_verification_time_seconds?: number | null;
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
  expertise_area?: string | null;
  is_active?: boolean;
}

// ── Request to POST /admin/experts/{id}/reset-password ──────────────
export interface ResetExpertPasswordRequest {
  new_password: string;
}

// ── Method distribution sub-object in PublicStats ────────────────────
export interface MethodDistribution {
  source_based: number;
  multimodal: number;
  photo_card: number;
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
  method_distribution: MethodDistribution;
  avg_verification_time_seconds?: number | null;
}

// ── Top claimed source from GET /dashboard/top-sources ───────────────
export interface TopSource {
  source: string;
  count: number;
}

// ── Fact Explorer — GET /dashboard/explorer ───────────────────────────
export interface ExplorerItem {
  submission_id: string;
  headline: string | null;
  submission_type: 'SOURCE_BASED' | 'MULTIMODAL' | 'PHOTO_CARD';
  claimed_source_text: string | null;
  final_label: 'TRUE' | 'FALSE' | 'PARTIALLY_TRUE' | 'NOT_FOUND_IN_CLAIMED_SOURCE' | null;
  confidence: number | null;
  published_date: string | null;
  created_at: string;
}

export interface ExplorerSearchParams {
  keyword?: string;
  verdict?: string;
  method?: string;
  date_from?: string;
  date_to?: string;
  source_id?: string;
  limit?: number;
  offset?: number;
}

export interface ExplorerSearchResponse {
  items: ExplorerItem[];
  total: number;
  limit: number;
  offset: number;
}

// ── Credibility weight tiers — admin-configurable, GET/POST/PUT/DELETE
//    /admin/credibility-tiers ───────────────────────────────────────
export interface CredibilityWeightTier {
  id: string;
  label: string;
  min_accuracy_pct: number;
  max_accuracy_pct: number;
  weight: number;
  is_active: boolean;
}

export interface CredibilityWeightTierRequest {
  label: string;
  min_accuracy_pct: number;
  max_accuracy_pct: number;
  weight: number;
  is_active?: boolean;
}

export interface CredibilityWeightTierUpdateRequest {
  label?: string;
  min_accuracy_pct?: number;
  max_accuracy_pct?: number;
  weight?: number;
  is_active?: boolean;
}
