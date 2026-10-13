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

@Injectable({ providedIn: 'root' })
export class AdminService {
  private readonly api = inject(ApiService);

  createExpert(body: CreateExpertRequest): Observable<ExpertResponse> {
    return this.api.post<ExpertResponse>(API_ENDPOINTS.ADMIN_EXPERTS, body);
  }

  listExperts(limit = 50, offset = 0, q = ''): Observable<ExpertResponse[]> {
    const params: Record<string, string | number> = { limit, offset };
    if (q.trim()) params['q'] = q.trim();
    return this.api.get<ExpertResponse[]>(API_ENDPOINTS.ADMIN_EXPERTS, params);
  }

  getExpert(id: string): Observable<ExpertResponse> {
    return this.api.get<ExpertResponse>(`${API_ENDPOINTS.ADMIN_EXPERTS}/${id}`);
  }

  updateExpert(id: string, body: UpdateExpertRequest): Observable<ExpertResponse> {
    return this.api.put<ExpertResponse>(`${API_ENDPOINTS.ADMIN_EXPERTS}/${id}`, body);
  }

  resetExpertPassword(
    id: string,
    body: ResetExpertPasswordRequest,
  ): Observable<{ message: string }> {
    return this.api.post<{ message: string }>(
      `${API_ENDPOINTS.ADMIN_EXPERTS}/${id}/reset-password`,
      body,
    );
  }

  deactivateExpert(id: string): Observable<ExpertResponse> {
    return this.api.post<ExpertResponse>(`${API_ENDPOINTS.ADMIN_EXPERTS}/${id}/deactivate`);
  }

  activateExpert(id: string): Observable<ExpertResponse> {
    return this.api.post<ExpertResponse>(`${API_ENDPOINTS.ADMIN_EXPERTS}/${id}/activate`);
  }

  getStats(): Observable<AdminStats> {
    return this.api.get<AdminStats>(API_ENDPOINTS.ADMIN_STATS);
  }

  getDashboard(): Observable<AdminDashboard> {
    return this.api.get<AdminDashboard>(API_ENDPOINTS.ADMIN_DASHBOARD);
  }

  listCredibilityTiers(): Observable<CredibilityWeightTier[]> {
    return this.api.get<CredibilityWeightTier[]>(API_ENDPOINTS.ADMIN_CREDIBILITY_TIERS);
  }

  saveCredibilityTiers(tiers: CredibilityWeightTierItem[]): Observable<CredibilityWeightTier[]> {
    return this.api.put<CredibilityWeightTier[]>(API_ENDPOINTS.ADMIN_CREDIBILITY_TIERS, { tiers });
  }

  getVotingConfig(): Observable<VotingConfig> {
    return this.api.get<VotingConfig>(API_ENDPOINTS.ADMIN_VOTING_CONFIG);
  }

  updateVotingConfig(body: VotingConfigUpdateRequest): Observable<VotingConfig> {
    return this.api.put<VotingConfig>(API_ENDPOINTS.ADMIN_VOTING_CONFIG, body);
  }
}
