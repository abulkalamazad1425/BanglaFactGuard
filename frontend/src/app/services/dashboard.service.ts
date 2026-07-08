import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { ApiService } from './api.service';
import { API_ENDPOINTS } from '../core/constants/api-endpoints.constant';
import { PublicStats, TopSource } from '../models/admin.model';

@Injectable({ providedIn: 'root' })
export class DashboardService {
  private readonly api = inject(ApiService);

  /** GET /api/v1/dashboard/stats */
  getPublicStats(): Observable<PublicStats> {
    return this.api.get<PublicStats>(API_ENDPOINTS.DASHBOARD_STATS);
  }

  /** GET /api/v1/dashboard/top-sources */
  getTopSources(limit = 10): Observable<TopSource[]> {
    return this.api.get<TopSource[]>(API_ENDPOINTS.DASHBOARD_TOP_SOURCES, { limit });
  }
}
