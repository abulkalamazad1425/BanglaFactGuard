import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { ApiService } from './api.service';
import { API_ENDPOINTS } from '../core/constants/api-endpoints.constant';
import {
  VerificationRequest,
  VerificationResponse,
  VerificationQueued,
  VerificationStatus,
  SubmissionSummary,
  SubmissionStats,
  MySubmissionFilters,
} from '../models/verification.model';
import {
  MultimodalPredictionDetail,
  MultimodalPredictionResult,
} from '../models/verification.model';

@Injectable({ providedIn: 'root' })
export class VerificationService {
  private readonly api = inject(ApiService);

  submit(request: VerificationRequest): Observable<{ submission_id: string }> {
    return this.api.post<{ submission_id: string }>(API_ENDPOINTS.VERIFICATION, request);
  }

  submitAsync(request: VerificationRequest): Observable<VerificationQueued> {
    return this.api.post<VerificationQueued>(API_ENDPOINTS.VERIFICATION_ASYNC, request);
  }

  getStatus(submissionId: string): Observable<VerificationStatus> {
    return this.api.get<VerificationStatus>(`${API_ENDPOINTS.VERIFICATION}/${submissionId}/status`);
  }

  getResult(submissionId: string): Observable<VerificationResponse> {
    return this.api.get<VerificationResponse>(`${API_ENDPOINTS.VERIFICATION}/${submissionId}`);
  }

  getMySubmissions(
    limit = 20,
    offset = 0,
    filters: MySubmissionFilters = {},
  ): Observable<SubmissionSummary[]> {
    const params: Record<string, string | number> = { limit, offset };
    if (filters.q?.trim()) params['q'] = filters.q.trim();
    if (filters.state) params['state'] = filters.state;
    if (filters.type) params['type'] = filters.type;
    return this.api.get<SubmissionSummary[]>(API_ENDPOINTS.USERS_SUBMISSIONS, params);
  }

  getMyStats(): Observable<SubmissionStats> {
    return this.api.get<SubmissionStats>(API_ENDPOINTS.USERS_SUBMISSION_STATS);
  }
}

@Injectable({ providedIn: 'root' })
export class MultimodalService {
  private readonly api = inject(ApiService);

  predict(headline: string, bodyText: string, image: File): Observable<MultimodalPredictionResult> {
    const fd = new FormData();
    fd.append('headline', headline);
    fd.append('body_text', bodyText);
    fd.append('image', image);
    return this.api.postFormData<MultimodalPredictionResult>(API_ENDPOINTS.MULTIMODAL_PREDICT, fd);
  }

  submitAsync(
    headline: string,
    bodyText: string,
    image: File,
  ): Observable<{ submission_id: string; status: string }> {
    const data = new FormData();
    data.append('headline', headline);
    data.append('body_text', bodyText);
    data.append('image', image);
    return this.api.postFormData<{ submission_id: string; status: string }>(
      API_ENDPOINTS.MULTIMODAL_PREDICT + '/async',
      data,
    );
  }

  getBySubmission(submissionId: string): Observable<MultimodalPredictionDetail> {
    return this.api.get<MultimodalPredictionDetail>(
      `${API_ENDPOINTS.MULTIMODAL_BY_SUBMISSION}/${submissionId}`,
    );
  }
}
