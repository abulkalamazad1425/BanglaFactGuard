import { Injectable, inject, signal } from '@angular/core';
import { interval } from 'rxjs';
import { switchMap, catchError, of } from 'rxjs';
import { API_ENDPOINTS } from '../constants/api-endpoints.constant';
import { UnreadCountResponse } from '../models/notification.model';
import { ApiService } from './api.service';
import { AuthService } from './auth.service';

@Injectable({ providedIn: 'root' })
export class NotificationService {
  private readonly api = inject(ApiService);
  private readonly auth = inject(AuthService);

  readonly unreadCount = signal<number>(0);

  startPolling(): void {
    // Poll every 60 seconds when user is logged in
    interval(60_000).pipe(
      switchMap(() => {
        if (!this.auth.isLoggedIn()) return of(null);
        return this.api.get<UnreadCountResponse>(API_ENDPOINTS.NOTIFICATIONS_COUNT).pipe(
          catchError(() => of(null))
        );
      })
    ).subscribe(res => {
      if (res) this.unreadCount.set(res.unread_count);
    });
  }

  refreshCount(): void {
    if (!this.auth.isLoggedIn()) return;
    this.api.get<UnreadCountResponse>(API_ENDPOINTS.NOTIFICATIONS_COUNT).subscribe({
      next: res => this.unreadCount.set(res.unread_count),
      error: () => {},
    });
  }
}
