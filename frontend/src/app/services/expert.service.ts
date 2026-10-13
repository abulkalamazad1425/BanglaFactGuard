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

@Injectable({ providedIn: 'root' })
export class ExpertService {
  private readonly api = inject(ApiService);

  getQueue(
    limit = 20,
    offset = 0,
    q = '',
    state: 'all' | 'escalated' | 'review' = 'all',
  ): Observable<ExpertQueueItem[]> {
    return this.api.get<ExpertQueueItem[]>(API_ENDPOINTS.EXPERT_QUEUE, { limit, offset, q, state });
  }

  getQueueItem(submissionId: string): Observable<ExpertQueueItem> {
    return this.api.get<ExpertQueueItem>(`${API_ENDPOINTS.EXPERT_QUEUE}/${submissionId}`);
  }

  submitVote(submissionId: string, body: ExpertVoteRequest): Observable<ExpertReviewResponse> {
    return this.api.post<ExpertReviewResponse>(
      `${API_ENDPOINTS.EXPERT_QUEUE}/${submissionId}/vote`,
      body,
    );
  }

  editVote(reviewId: string, body: ExpertVoteUpdateRequest): Observable<ExpertReviewResponse> {
    return this.api.put<ExpertReviewResponse>(`${API_ENDPOINTS.EXPERT_REVIEWS}/${reviewId}`, body);
  }

  getHistory(limit = 50, offset = 0, q = ''): Observable<ExpertHistoryItem[]> {
    return this.api.get<ExpertHistoryItem[]>(API_ENDPOINTS.EXPERT_HISTORY, { limit, offset, q });
  }

  getStats(): Observable<ExpertStats> {
    return this.api.get<ExpertStats>(API_ENDPOINTS.EXPERT_STATS);
  }

  getCredibility(): Observable<CredibilityScore> {
    return this.api.get<CredibilityScore>('/expert/credibility');
  }
}
