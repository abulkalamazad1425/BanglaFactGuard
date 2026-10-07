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
} from '../models/verification.model';
import {
  MultimodalPredictionDetail,
  MultimodalPredictionResult,
} from '../models/verification.model';

// ── Verification Service ──────────────────────────────────────────────
// Covers: POST /api/v1/verify  →  GET /api/v1/verify/{id}
@Injectable({ providedIn: 'root' })
export class VerificationService {
  private readonly api = inject(ApiService);

  /** POST /api/v1/verify — submit a verification request */
  submit(request: VerificationRequest): Observable<{ submission_id: string }> {
    return this.api.post<{ submission_id: string }>(API_ENDPOINTS.VERIFICATION, request);
  }

  /**
   * POST /api/v1/verify/async — queue the claim and return straight away.
   * The pipeline takes up to a minute, so the caller polls `getStatus` (or
   * simply leaves the page and picks the result up from their history).
   */
  submitAsync(request: VerificationRequest): Observable<VerificationQueued> {
    return this.api.post<VerificationQueued>(API_ENDPOINTS.VERIFICATION_ASYNC, request);
  }

  /** GET /api/v1/verify/{submission_id}/status — poll a queued verification */
  getStatus(submissionId: string): Observable<VerificationStatus> {
    return this.api.get<VerificationStatus>(`${API_ENDPOINTS.VERIFICATION}/${submissionId}/status`);
  }

  /** GET /api/v1/verify/{submission_id} — fetch the full result */
  getResult(submissionId: string): Observable<VerificationResponse> {
    return this.api.get<VerificationResponse>(`${API_ENDPOINTS.VERIFICATION}/${submissionId}`);
  }

  /** GET /api/v1/users/me/submissions — submission history */
  getMySubmissions(limit = 20, offset = 0): Observable<SubmissionSummary[]> {
    return this.api.get<SubmissionSummary[]>(API_ENDPOINTS.USERS_SUBMISSIONS, { limit, offset });
  }

  /** GET /api/v1/users/me/submissions/stats */
  getMyStats(): Observable<SubmissionStats> {
    return this.api.get<SubmissionStats>(API_ENDPOINTS.USERS_SUBMISSION_STATS);
  }
}

// ── Multimodal Service ───────────────────────────────────────────────
// Covers: POST /api/v1/multimodal/predict (multipart/form-data)
@Injectable({ providedIn: 'root' })
export class MultimodalService {
  private readonly api = inject(ApiService);

  /** POST /api/v1/multimodal/predict — headline + body_text + image */
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

  /** GET /api/v1/multimodal/by-submission/{submission_id} */
  getBySubmission(submissionId: string): Observable<MultimodalPredictionDetail> {
    return this.api.get<MultimodalPredictionDetail>(
      `${API_ENDPOINTS.MULTIMODAL_BY_SUBMISSION}/${submissionId}`,
    );
  }
}
