import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { ApiService } from './api.service';
import { API_ENDPOINTS } from '../core/constants/api-endpoints.constant';
import { PublicVotingDetails, SubmissionLookup } from '../models/verification.model';

@Injectable({ providedIn: 'root' })
export class SubmissionsService {
  private readonly api = inject(ApiService);

  getLookup(submissionId: string): Observable<SubmissionLookup> {
    return this.api.get<SubmissionLookup>(`${API_ENDPOINTS.SUBMISSIONS}/${submissionId}`);
  }

  getVotingDetails(submissionId: string): Observable<PublicVotingDetails> {
    return this.api.get<PublicVotingDetails>(
      `${API_ENDPOINTS.SUBMISSIONS}/${submissionId}/voting-details`,
    );
  }
}
