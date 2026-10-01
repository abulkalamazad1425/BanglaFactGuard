// ============================================================
// Admin Models — synced with backend admin/schemas.py
// ============================================================

import { ContentStatus, DateStatus, SourceStatus } from './verification.model';

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
// Source, content and date are independent dimensions — each gets its own
// pair of counts rather than being collapsed into one 4-way tally.
export interface VerdictBreakdown {
  source_confirmed_count: number;
  source_not_found_count: number;
  content_matched_count: number;
  content_altered_count: number;
  date_matched_count: number;
  date_mismatched_count: number;
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
  source_confirmed_count: number;
  source_not_found_count: number;
  content_matched_count: number;
  content_altered_count: number;
  date_matched_count: number;
  date_mismatched_count: number;
  pending_count: number;
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
  source_status: SourceStatus | null;
  content_status: ContentStatus | null;
  date_status: DateStatus | null;
  confidence: number | null;
  published_date: string | null;
  created_at: string;
}

export interface ExplorerSearchParams {
  keyword?: string;
  source_status?: string;
  content_status?: string;
  date_status?: string;
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
