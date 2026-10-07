import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { ApiService } from './api.service';
import { API_ENDPOINTS } from '../core/constants/api-endpoints.constant';
import {
  PhotoCardAccepted,
  PhotoCardResultResponse,
  PhotoCardVerifyRequest,
} from '../models/photocard.model';

// ── Photo Card Service ────────────────────────────────────────────────
// Background submission of the image only: the card is stored and a durable
// server-side job is queued, then the API answers 202 straight away. Gemini
// reads the headline, outlet and date from the original image and the claim
// is verified on the server whether or not the browser stays open; the result
// is read by submission id.
@Injectable({ providedIn: 'root' })
export class PhotoCardService {
  private readonly api = inject(ApiService);

  private toForm(request: PhotoCardVerifyRequest): FormData {
    const fd = new FormData();
    fd.append('image', request.image);
    return fd;
  }

  /** POST /photocard/verify/async — returns 202 once the image is stored and the job is queued. */
  submitAsync(request: PhotoCardVerifyRequest): Observable<PhotoCardAccepted> {
    return this.api.postFormData<PhotoCardAccepted>(
      API_ENDPOINTS.PHOTOCARD_VERIFY_ASYNC,
      this.toForm(request),
    );
  }

  /** GET /photocard/{submission_id} — current state: pending, processing, failed or the saved report. */
  getResult(submissionId: string): Observable<PhotoCardResultResponse> {
    return this.api.get<PhotoCardResultResponse>(`${API_ENDPOINTS.PHOTOCARD}/${submissionId}`);
  }
}
