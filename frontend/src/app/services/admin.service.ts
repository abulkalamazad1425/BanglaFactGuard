import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { ApiService } from './api.service';
import { API_ENDPOINTS } from '../core/constants/api-endpoints.constant';
import {
  ExpertResponse,
  AdminDashboard,
  AdminStats,
  CreateExpertRequest,
  UpdateExpertRequest,
  ResetExpertPasswordRequest,
  CredibilityWeightTier,
  CredibilityWeightTierItem,
  VotingConfig,
  VotingConfigUpdateRequest,
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

  /** GET /api/v1/admin/experts?limit=&offset=&q= (q: name, email or expertise) */
  listExperts(limit = 50, offset = 0, q = ''): Observable<ExpertResponse[]> {
    const params: Record<string, string | number> = { limit, offset };
    if (q.trim()) params['q'] = q.trim();
    return this.api.get<ExpertResponse[]>(API_ENDPOINTS.ADMIN_EXPERTS, params);
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
  resetExpertPassword(
    id: string,
    body: ResetExpertPasswordRequest,
  ): Observable<{ message: string }> {
    return this.api.post<{ message: string }>(
      `${API_ENDPOINTS.ADMIN_EXPERTS}/${id}/reset-password`,
      body,
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

  /** GET /api/v1/admin/dashboard */
  getDashboard(): Observable<AdminDashboard> {
    return this.api.get<AdminDashboard>(API_ENDPOINTS.ADMIN_DASHBOARD);
  }

  /** GET /api/v1/admin/credibility-tiers */
  listCredibilityTiers(): Observable<CredibilityWeightTier[]> {
    return this.api.get<CredibilityWeightTier[]>(API_ENDPOINTS.ADMIN_CREDIBILITY_TIERS);
  }

  /** PUT /api/v1/admin/credibility-tiers — saves the complete tier set in one
   *  transaction; the server checks that the active tiers cover 0–100%. */
  saveCredibilityTiers(tiers: CredibilityWeightTierItem[]): Observable<CredibilityWeightTier[]> {
    return this.api.put<CredibilityWeightTier[]>(API_ENDPOINTS.ADMIN_CREDIBILITY_TIERS, { tiers });
  }

  /** GET /api/v1/admin/voting-config */
  getVotingConfig(): Observable<VotingConfig> {
    return this.api.get<VotingConfig>(API_ENDPOINTS.ADMIN_VOTING_CONFIG);
  }

  /** PUT /api/v1/admin/voting-config */
  updateVotingConfig(body: VotingConfigUpdateRequest): Observable<VotingConfig> {
    return this.api.put<VotingConfig>(API_ENDPOINTS.ADMIN_VOTING_CONFIG, body);
  }
}
