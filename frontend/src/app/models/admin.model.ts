import {
  ContentStatus,
  DateStatus,
  HeadlineAlterationStatus,
  OverallVerdict,
  SourceStatus,
} from './verification.model';

export interface ExpertResponse {
  id: string;
  email: string;
  full_name: string | null;
  is_active: boolean;
  role: string;
  expertise_area?: string | null;
  credibility_score?: number | null;
  total_votes?: number | null;
  correct_votes?: number | null;
  created_at: string;
}

export interface AdminStats {
  total_submissions: number;
  submissions_last_30_days: number;
  total_experts: number;
  active_experts: number;
  pending_expert_reviews: number;
  escalated_claims?: number;
  avg_verification_time_seconds?: number | null;
}

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

export interface CreateExpertRequest {
  email: string;
  password: string;
  full_name?: string | null;
}

export interface UpdateExpertRequest {
  full_name?: string | null;
  email?: string | null;
  expertise_area?: string | null;
  is_active?: boolean;
}

export interface ResetExpertPasswordRequest {
  new_password: string;
}

export interface MethodDistribution {
  source_based: number;
  multimodal: number;
  photo_card: number;
}

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

export interface TopSource {
  source: string;
  count: number;
}

export interface ExplorerItem {
  prediction?: string | null;
  submission_id: string;
  headline: string | null;
  submission_type: 'SOURCE_BASED' | 'MULTIMODAL' | 'PHOTO_CARD';
  claimed_source_text: string | null;
  overall_verdict: OverallVerdict | null;
  is_finalized: boolean;
  source_status: SourceStatus | null;
  content_status: ContentStatus | null;
  headline_status?: HeadlineAlterationStatus | null;
  date_status: DateStatus | null;
  confidence: number | null;
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

export interface CredibilityWeightTier {
  id: string;
  label: string;
  min_accuracy_pct: number;
  max_accuracy_pct: number;
  weight: number;
  is_active: boolean;
}

export interface CredibilityWeightTierItem {
  id?: string | null;
  label: string;
  min_accuracy_pct: number;
  max_accuracy_pct: number;
  weight: number;
  is_active: boolean;
}

export interface VotingConfig {
  id: string;
  min_expert_votes: number;
  activation_threshold_votes: number;
  verified_threshold: number;
  lead_margin: number;
  max_review_votes: number | null;
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
