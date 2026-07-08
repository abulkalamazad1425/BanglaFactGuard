import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { ApiService } from './api.service';
import { API_ENDPOINTS } from '../core/constants/api-endpoints.constant';
import {
  ExpertQueueItem,
  ExpertReviewResponse,
  ExpertHistoryItem,
  ExpertStats,
  CredibilityScore,
  ExpertVoteRequest,
  ExpertVoteUpdateRequest,
} from '../models/expert.model';

// ── Expert Service ────────────────────────────────────────────────────
// Covers backend expert_review/router.py endpoints
@Injectable({ providedIn: 'root' })
export class ExpertService {
  private readonly api = inject(ApiService);

  /** GET /api/v1/expert/queue */
  getQueue(limit = 20, offset = 0): Observable<ExpertQueueItem[]> {
    return this.api.get<ExpertQueueItem[]>(API_ENDPOINTS.EXPERT_QUEUE, { limit, offset });
  }

  /** GET /api/v1/expert/queue/{claim_id} — not in current router but reserved */
  getQueueItem(claimId: string): Observable<ExpertQueueItem> {
    return this.api.get<ExpertQueueItem>(`${API_ENDPOINTS.EXPERT_QUEUE}/${claimId}`);
  }

  /** POST /api/v1/expert/queue/{claim_id}/vote */
  submitVote(claimId: string, body: ExpertVoteRequest): Observable<ExpertReviewResponse> {
    return this.api.post<ExpertReviewResponse>(
      `${API_ENDPOINTS.EXPERT_QUEUE}/${claimId}/vote`,
      body
    );
  }

  /** PUT /api/v1/expert/reviews/{review_id} */
  editVote(reviewId: string, body: ExpertVoteUpdateRequest): Observable<ExpertReviewResponse> {
    return this.api.put<ExpertReviewResponse>(
      `${API_ENDPOINTS.EXPERT_REVIEWS}/${reviewId}`,
      body
    );
  }

  /** GET /api/v1/expert/history */
  getHistory(limit = 50, offset = 0): Observable<ExpertHistoryItem[]> {
    return this.api.get<ExpertHistoryItem[]>(API_ENDPOINTS.EXPERT_HISTORY, { limit, offset });
  }

  /** GET /api/v1/expert/stats */
  getStats(): Observable<ExpertStats> {
    return this.api.get<ExpertStats>(API_ENDPOINTS.EXPERT_STATS);
  }

  /** GET /api/v1/expert/credibility */
  getCredibility(): Observable<CredibilityScore> {
    return this.api.get<CredibilityScore>('/expert/credibility');
  }
}
