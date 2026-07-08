import { Injectable, inject, signal } from '@angular/core';
import { Observable } from 'rxjs';
import { tap } from 'rxjs/operators';
import { ApiService } from './api.service';
import { API_ENDPOINTS } from '../core/constants/api-endpoints.constant';
import { NotificationItem, UnreadCountResponse } from '../models/notification.model';
import { AuthService } from './auth.service';
import { of } from 'rxjs';

// ── Notification Service ──────────────────────────────────────────────
// Covers backend notifications/router.py endpoints
@Injectable({ providedIn: 'root' })
export class NotificationService {
  private readonly api = inject(ApiService);
  private readonly auth = inject(AuthService);

  /** Reactive unread count — used by navbar and notification-list */
  readonly unreadCount = signal<number>(0);

  constructor() {
    // Load initial count on service init (silent, no error propagation needed)
    this.refreshCount();
  }

  /** GET /api/v1/notifications?limit=&offset=&unread_only= */
  list(limit = 30, offset = 0, unreadOnly = false): Observable<NotificationItem[]> {
    return this.api.get<NotificationItem[]>(API_ENDPOINTS.NOTIFICATIONS, {
      limit,
      offset,
      unread_only: unreadOnly,
    });
  }

  /** GET /api/v1/notifications/count — also updates the unreadCount signal */
  getUnreadCount(): Observable<UnreadCountResponse> {
    if (!this.auth.isLoggedIn()) {
      return of({ unread_count: 0 });
    }
    return this.api.get<UnreadCountResponse>(API_ENDPOINTS.NOTIFICATIONS_COUNT).pipe(
      tap(r => this.unreadCount.set(r.unread_count))
    );
  }

  /** Refresh the unread count signal silently */
  refreshCount(): void {
    this.getUnreadCount().subscribe({ error: () => {} });
  }

  /** POST /api/v1/notifications/{id}/read */
  markRead(id: string): Observable<void> {
    return this.api.post<void>(`${API_ENDPOINTS.NOTIFICATIONS}/${id}/read`);
  }

  /** POST /api/v1/notifications/read-all */
  markAllRead(): Observable<void> {
    return this.api.post<void>(API_ENDPOINTS.NOTIFICATIONS_READ_ALL).pipe(
      tap(() => this.unreadCount.set(0))
    );
  }

  /** Start periodic polling every 60s (call once in AppComponent) */
  startPolling(intervalMs = 60_000): void {
    setInterval(() => this.refreshCount(), intervalMs);
  }
}
