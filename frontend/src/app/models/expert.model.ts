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
  can_vote?: boolean;
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
  image_url?: string | null;
  headline_check_status?: HeadlineCheckStatus | null;
  headline_alteration?: HeadlineAlterationDetail | null;
  body_similarity?: BodySimilarityReport | null;
}

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

export interface ExpertStats {
  user_id: string;
  full_name: string | null;
  total_votes: number;
  correct_votes: number;
  accuracy_pct: number | null;
  current_credibility: number | null;
  activation_threshold: number;
}

export interface CredibilityScore {
  user_id: string;
  score: number | null;
  total_votes: number;
  correct_votes: number;
  updated_at: string;
}

export interface ExpertVoteRequest {
  overall_verdict: OverallVerdict;
  source_status?: SourceStatus | null;
  content_status?: ContentStatus | null;
  date_status?: DateStatus | null;
  justification: string;
}

export interface ExpertVoteUpdateRequest {
  overall_verdict?: OverallVerdict | null;
  source_status?: SourceStatus | null;
  content_status?: ContentStatus | null;
  date_status?: DateStatus | null;
  justification?: string | null;
}
