import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { ApiService } from './api.service';
import { API_ENDPOINTS } from '../core/constants/api-endpoints.constant';
import {
  ExpertResponse,
  AdminStats,
  CreateExpertRequest,
  UpdateExpertRequest,
  ResetExpertPasswordRequest,
  CredibilityWeightTier,
  CredibilityWeightTierRequest,
  CredibilityWeightTierUpdateRequest,
} from '../models/admin.model';

// ── Admin Service ─────────────────────────────────────────────────────
// Covers backend admin/router.py endpoints
@Injectable({ providedIn: 'root' })
export class AdminService {
  private readonly api = inject(ApiService);

  /** POST /api/v1/admin/experts */
  createExpert(body: CreateExpertRequest): Observable<ExpertResponse> {
    return this.api.post<ExpertResponse>(API_ENDPOINTS.ADMIN_EXPERTS, body);
  }

  /** GET /api/v1/admin/experts?limit=&offset= */
  listExperts(limit = 50, offset = 0): Observable<ExpertResponse[]> {
    return this.api.get<ExpertResponse[]>(API_ENDPOINTS.ADMIN_EXPERTS, { limit, offset });
  }

  /** GET /api/v1/admin/experts/{id} */
  getExpert(id: string): Observable<ExpertResponse> {
    return this.api.get<ExpertResponse>(`${API_ENDPOINTS.ADMIN_EXPERTS}/${id}`);
  }

  /** PUT /api/v1/admin/experts/{id} */
  updateExpert(id: string, body: UpdateExpertRequest): Observable<ExpertResponse> {
    return this.api.put<ExpertResponse>(`${API_ENDPOINTS.ADMIN_EXPERTS}/${id}`, body);
  }

  /** POST /api/v1/admin/experts/{id}/reset-password */
  resetExpertPassword(id: string, body: ResetExpertPasswordRequest): Observable<{ message: string }> {
    return this.api.post<{ message: string }>(
      `${API_ENDPOINTS.ADMIN_EXPERTS}/${id}/reset-password`,
      body
    );
  }

  /** POST /api/v1/admin/experts/{id}/deactivate */
  deactivateExpert(id: string): Observable<ExpertResponse> {
    return this.api.post<ExpertResponse>(`${API_ENDPOINTS.ADMIN_EXPERTS}/${id}/deactivate`);
  }

  /** POST /api/v1/admin/experts/{id}/activate */
  activateExpert(id: string): Observable<ExpertResponse> {
    return this.api.post<ExpertResponse>(`${API_ENDPOINTS.ADMIN_EXPERTS}/${id}/activate`);
  }

  /** GET /api/v1/admin/stats */
  getStats(): Observable<AdminStats> {
    return this.api.get<AdminStats>(API_ENDPOINTS.ADMIN_STATS);
  }

  /** GET /api/v1/admin/credibility-tiers */
  listCredibilityTiers(): Observable<CredibilityWeightTier[]> {
    return this.api.get<CredibilityWeightTier[]>(API_ENDPOINTS.ADMIN_CREDIBILITY_TIERS);
  }

  /** POST /api/v1/admin/credibility-tiers */
  createCredibilityTier(body: CredibilityWeightTierRequest): Observable<CredibilityWeightTier> {
    return this.api.post<CredibilityWeightTier>(API_ENDPOINTS.ADMIN_CREDIBILITY_TIERS, body);
  }

  /** PUT /api/v1/admin/credibility-tiers/{id} */
  updateCredibilityTier(
    id: string,
    body: CredibilityWeightTierUpdateRequest
  ): Observable<CredibilityWeightTier> {
    return this.api.put<CredibilityWeightTier>(
      `${API_ENDPOINTS.ADMIN_CREDIBILITY_TIERS}/${id}`,
      body
    );
  }

  /** DELETE /api/v1/admin/credibility-tiers/{id} */
  deleteCredibilityTier(id: string): Observable<void> {
    return this.api.delete<void>(`${API_ENDPOINTS.ADMIN_CREDIBILITY_TIERS}/${id}`);
  }
}
