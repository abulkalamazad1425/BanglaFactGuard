import { Injectable, inject, signal, effect } from '@angular/core';
import { Observable } from 'rxjs';
import { tap } from 'rxjs/operators';
import { ApiService } from './api.service';
import { API_ENDPOINTS } from '../core/constants/api-endpoints.constant';
import { NotificationItem, UnreadCountResponse } from '../models/notification.model';
import { AuthService } from './auth.service';
import { of } from 'rxjs';

@Injectable({ providedIn: 'root' })
export class NotificationService {
  private readonly api = inject(ApiService);
  private readonly auth = inject(AuthService);

  readonly unreadCount = signal<number>(0);

  constructor() {
    effect(() => {
      this.auth.user();
      this.unreadCount.set(0);
      this.refreshCount();
    });
  }

  list(limit = 30, offset = 0, unreadOnly = false): Observable<NotificationItem[]> {
    return this.api.get<NotificationItem[]>(API_ENDPOINTS.NOTIFICATIONS, {
      limit,
      offset,
      unread_only: unreadOnly,
    });
  }

  getUnreadCount(): Observable<UnreadCountResponse> {
    if (!this.auth.isLoggedIn()) {
      return of({ unread_count: 0 });
    }
    return this.api
      .get<UnreadCountResponse>(API_ENDPOINTS.NOTIFICATIONS_COUNT)
      .pipe(tap((r) => this.unreadCount.set(r.unread_count)));
  }

  refreshCount(): void {
    this.getUnreadCount().subscribe({ error: () => {} });
  }

  markRead(id: string): Observable<void> {
    return this.api.post<void>(`${API_ENDPOINTS.NOTIFICATIONS}/${id}/read`);
  }

  markAllRead(): Observable<void> {
    return this.api
      .post<void>(API_ENDPOINTS.NOTIFICATIONS_READ_ALL)
      .pipe(tap(() => this.unreadCount.set(0)));
  }

  startPolling(intervalMs = 15_000): void {
    setInterval(() => this.refreshCount(), intervalMs);
  }
}
