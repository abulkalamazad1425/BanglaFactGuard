// ============================================================
// Admin Models — synced with backend admin/schemas.py
// ============================================================

import { ContentStatus, DateStatus, HeadlineAlterationStatus, OverallVerdict, SourceStatus } from './verification.model';

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

// ── Platform-wide admin stats from GET /admin/stats ─────────────────
export interface AdminStats {
  total_submissions: number;
  submissions_last_30_days: number;
  total_experts: number;
  active_experts: number;
  /** Claims currently open for expert voting. */
  pending_expert_reviews: number;
  /** Claims awaiting an admin decision. */
  escalated_claims?: number;
  avg_verification_time_seconds?: number | null;
}

// ── Admin home from GET /admin/dashboard ─────────────────────────────
export interface DashboardClaim {
  submission_id: string;
  headline: string | null;
  submission_type: string;
  status: string;
  vote_count: number;
  submitted_at: string;
  escalated_at?: string | null;
  final_verdict?: OverallVerdict | null;
  decided_by_admin: boolean;
  finalized_at?: string | null;
}

export interface DashboardExpert {
  id: string;
  full_name: string | null;
  is_active: boolean;
  total_votes: number;
  last_vote_at?: string | null;
}

export interface DashboardActivity {
  kind: 'VOTE' | 'ADMIN_DECISION';
  actor: string;
  submission_id: string;
  headline: string | null;
  overall_vote: OverallVerdict;
  at: string;
}

export interface AdminDashboard {
  escalated_count: number;
  pending_review_count: number;
  processing_count: number;
  failed_last_7_days: number;
  submissions_last_7_days: number;
  finalized_last_7_days: number;
  total_submissions: number;
  active_experts: number;
  inactive_experts: number;
  escalated_claims: DashboardClaim[];
  oldest_pending_reviews: DashboardClaim[];
  recent_submissions: DashboardClaim[];
  recent_decisions: DashboardClaim[];
  experts: DashboardExpert[];
  recent_activity: DashboardActivity[];
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
  prediction?: string | null;
  submission_id: string;
  headline: string | null;
  submission_type: 'SOURCE_BASED' | 'MULTIMODAL' | 'PHOTO_CARD';
  claimed_source_text: string | null;
  /** The expert-finalized Overall verdict; null until experts finalize it
   *  (the automated system never sets it for source-based/photo-card claims). */
  overall_verdict: OverallVerdict | null;
  /** True once expert review has finalized overall_verdict. */
  is_finalized: boolean;
  source_status: SourceStatus | null;
  content_status: ContentStatus | null;
  /** Exact Matched / Meaning Preserved / Altered — the AI's preliminary finding. */
  headline_status?: HeadlineAlterationStatus | null;
  date_status: DateStatus | null;
  confidence: number | null;
  /** Thumbnail for MULTIMODAL/PHOTO_CARD submissions. */
  image_url?: string | null;
  published_date: string | null;
  created_at: string;
}

export interface ExplorerSearchParams {
  review_state?: 'finalized' | 'review';
  keyword?: string;
  source_status?: string;
  content_status?: string;
  date_status?: string;
  /** Matches only expert-finalized claims; spans every submission type. */
  overall_verdict?: string;
  method?: string;
  date_from?: string;
  date_to?: string;
  source_id?: string;
  limit?: number;
  offset?: number;
}

export interface ExplorerSearchResponse {
  archive_summary?: { total: number; finalized: number; review: number };
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

// ── Voting configuration — admin-configurable, GET/PUT /admin/voting-config.
//    No fixed limit in code; the admin decides how many expert votes a
//    claim needs before it's finalized. ───────────────────────────────
export interface VotingConfig {
  id: string;
  /** M — minimum votes before a claim can finalize */
  min_expert_votes: number;
  /** N — lifetime votes an expert needs before their tier weight applies */
  activation_threshold_votes: number;
  /** T — weighted score the leading verdict must reach */
  verified_threshold: number;
  /** Leader's score must exceed the runner-up's by at least this */
  lead_margin: number;
  /** Escalate to admin once this many votes are cast without a final decision (null = not configured) */
  max_review_votes: number | null;
  /** Escalate to admin once this many hours pass since submission without a final decision (null = not configured) */
  max_review_hours: number | null;
  updated_at: string;
}

export interface VotingConfigUpdateRequest {
  min_expert_votes?: number;
  activation_threshold_votes?: number;
  verified_threshold?: number;
  lead_margin?: number;
  max_review_votes?: number | null;
  max_review_hours?: number | null;
}
