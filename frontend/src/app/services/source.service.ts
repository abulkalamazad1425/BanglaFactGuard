import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { ApiService } from './api.service';
import { API_ENDPOINTS } from '../core/constants/api-endpoints.constant';
import {
  SourceCreateRequest,
  SourceListResponse,
  SourceResponse,
  SourceUpdateRequest,
} from '../models/source.model';

@Injectable({ providedIn: 'root' })
export class SourceService {
  private readonly api = inject(ApiService);

  listSources(
    language?: string,
    page: number = 1,
    size: number = 20,
    includeInactive: boolean = false,
  ): Observable<SourceListResponse> {
    const params: any = { page, size };
    if (language) params.language = language;
    if (includeInactive) params.include_inactive = true;
    return this.api.get<SourceListResponse>(API_ENDPOINTS.SOURCES, params);
  }

  createSource(body: SourceCreateRequest): Observable<SourceResponse> {
    return this.api.post<SourceResponse>(API_ENDPOINTS.SOURCES, body);
  }

  getSource(id: string): Observable<SourceResponse> {
    return this.api.get<SourceResponse>(`${API_ENDPOINTS.SOURCES}/${id}`);
  }

  updateSource(id: string, body: SourceUpdateRequest): Observable<SourceResponse> {
    return this.api.put<SourceResponse>(`${API_ENDPOINTS.SOURCES}/${id}`, body);
  }

  deleteSource(id: string): Observable<void> {
    return this.api.delete<void>(`${API_ENDPOINTS.SOURCES}/${id}`);
  }
}
