import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { ApiService } from './api.service';
import { API_ENDPOINTS } from '../core/constants/api-endpoints.constant';
import {
  PhotoCardAccepted,
  PhotoCardResultResponse,
  PhotoCardVerifyRequest,
} from '../models/photocard.model';

@Injectable({ providedIn: 'root' })
export class PhotoCardService {
  private readonly api = inject(ApiService);

  private toForm(request: PhotoCardVerifyRequest): FormData {
    const fd = new FormData();
    fd.append('image', request.image);
    return fd;
  }

  submitAsync(request: PhotoCardVerifyRequest): Observable<PhotoCardAccepted> {
    return this.api.postFormData<PhotoCardAccepted>(
      API_ENDPOINTS.PHOTOCARD_VERIFY_ASYNC,
      this.toForm(request),
    );
  }

  getResult(submissionId: string): Observable<PhotoCardResultResponse> {
    return this.api.get<PhotoCardResultResponse>(`${API_ENDPOINTS.PHOTOCARD}/${submissionId}`);
  }
}
