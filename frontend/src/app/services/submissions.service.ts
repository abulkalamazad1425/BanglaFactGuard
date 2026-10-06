import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { ApiService } from './api.service';
import { API_ENDPOINTS } from '../core/constants/api-endpoints.constant';
import { PublicVotingDetails, SubmissionLookup } from '../models/verification.model';

/**
 * Type-agnostic submission lookup.
 *
 * Fact Explorer, submission history and notification links all carry only a
 * submission_id — they don't know (or need to know) whether it names a
 * source-based claim, a multimodal check, or a photo card. This is the first
 * call a result page makes to find out, before fetching the type-specific
 * detail from the right endpoint.
 */
@Injectable({ providedIn: 'root' })
export class SubmissionsService {
  private readonly api = inject(ApiService);

  /** GET /api/v1/submissions/{id} */
  getLookup(submissionId: string): Observable<SubmissionLookup> {
    return this.api.get<SubmissionLookup>(`${API_ENDPOINTS.SUBMISSIONS}/${submissionId}`);
  }

  /** GET /api/v1/submissions/{id}/voting-details — public, 404 until the final decision. */
  getVotingDetails(submissionId: string): Observable<PublicVotingDetails> {
    return this.api.get<PublicVotingDetails>(`${API_ENDPOINTS.SUBMISSIONS}/${submissionId}/voting-details`);
  }
}
