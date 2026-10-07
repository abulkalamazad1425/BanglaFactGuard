import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { ApiService } from './api.service';
import { API_ENDPOINTS } from '../core/constants/api-endpoints.constant';
import {
  PublicStats,
  TopSource,
  ExplorerSearchParams,
  ExplorerSearchResponse,
} from '../models/admin.model';

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

  /** GET /api/v1/dashboard/explorer — Fact Explorer search/browse */
  searchExplorer(params: ExplorerSearchParams): Observable<ExplorerSearchResponse> {
    const query: Record<string, string | number | boolean> = {};
    if (params.review_state) query['review_state'] = params.review_state;
    if (params.keyword) query['keyword'] = params.keyword;
    if (params.source_status) query['source_status'] = params.source_status;
    if (params.content_status) query['content_status'] = params.content_status;
    if (params.date_status) query['date_status'] = params.date_status;
    if (params.overall_verdict) query['overall_verdict'] = params.overall_verdict;
    if (params.method) query['method'] = params.method;
    if (params.date_from) query['date_from'] = params.date_from;
    if (params.date_to) query['date_to'] = params.date_to;
    if (params.source_id) query['source_id'] = params.source_id;
    query['limit'] = params.limit ?? 20;
    query['offset'] = params.offset ?? 0;
    return this.api.get<ExplorerSearchResponse>(API_ENDPOINTS.DASHBOARD_EXPLORER, query);
  }
}
