import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { ApiService } from './api.service';
import { API_ENDPOINTS } from '../core/constants/api-endpoints.constant';
import {
  PhotoCardExtractResponse,
  PhotoCardResultResponse,
  PhotoCardVerifyRequest,
  PhotoCardVerifyResponse,
} from '../models/photocard.model';

// ── Photo Card Service ────────────────────────────────────────────────
// Two-step flow:
//   1. POST /photocard/extract  — OCR the card, return a draft claim
//   2. POST /photocard/verify   — verify the text the user confirmed
@Injectable({ providedIn: 'root' })
export class PhotoCardService {
  private readonly api = inject(ApiService);

  /** Step 1 — upload the card and get back the extracted claim draft. */
  extract(image: File): Observable<PhotoCardExtractResponse> {
    const fd = new FormData();
    fd.append('image', image);
    return this.api.postFormData<PhotoCardExtractResponse>(
      API_ENDPOINTS.PHOTOCARD_EXTRACT,
      fd,
    );
  }

  /** Step 2 — verify the confirmed claim against its claimed source. */
  verify(request: PhotoCardVerifyRequest): Observable<PhotoCardVerifyResponse> {
    return this.api.post<PhotoCardVerifyResponse>(API_ENDPOINTS.PHOTOCARD_VERIFY, request);
  }

  /** GET /photocard/{submission_id} — a stored photo-card report. */
  getResult(submissionId: string): Observable<PhotoCardResultResponse> {
    return this.api.get<PhotoCardResultResponse>(
      `${API_ENDPOINTS.PHOTOCARD}/${submissionId}`,
    );
  }
}
