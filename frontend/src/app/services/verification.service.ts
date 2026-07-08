import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { ApiService } from './api.service';
import { API_ENDPOINTS } from '../core/constants/api-endpoints.constant';
import {
  VerificationRequest,
  VerificationResponse,
  SubmissionSummary,
  SubmissionStats,
} from '../models/verification.model';
import { MultimodalPredictionResult } from '../models/verification.model';

// ── Verification Service ──────────────────────────────────────────────
// Covers: POST /api/v1/verify  →  GET /api/v1/verify/{id}
@Injectable({ providedIn: 'root' })
export class VerificationService {
  private readonly api = inject(ApiService);

  /** POST /api/v1/verify — submit a verification request */
  submit(request: VerificationRequest): Observable<{ claim_id: string }> {
    return this.api.post<{ claim_id: string }>(API_ENDPOINTS.VERIFICATION, request);
  }

  /** GET /api/v1/verify/{claim_id} — fetch the full result */
  getResult(claimId: string): Observable<VerificationResponse> {
    return this.api.get<VerificationResponse>(`${API_ENDPOINTS.VERIFICATION}/${claimId}`);
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
}
