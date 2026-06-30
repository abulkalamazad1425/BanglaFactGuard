import { Component, OnInit, inject, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { ApiService } from '../../../core/services/api.service';
import { NotificationService } from '../../../core/services/notification.service';
import { Notification } from '../../../core/models/notification.model';
import { API_ENDPOINTS } from '../../../core/constants/api-endpoints.constant';
import { ToastService } from '../../../shared/services/toast.service';

@Component({
  selector: 'app-notification-list',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="notif-page">
      <div class="container container-sm" style="padding-top:48px; padding-bottom:80px;">
        <div class="page-header animate-in">
          <div class="header-content">
            <h1>Notifications</h1>
            @if (hasUnread()) {
              <button class="btn btn-secondary btn-sm" (click)="markAllRead()">
                Mark all as read
              </button>
            }
          </div>
        </div>

        @if (loading()) { <div class="loading-overlay"><div class="spinner"></div></div> }

        @if (!loading() && notifications().length === 0) {
          <div class="empty-state card text-center">
            <div style="font-size:64px;margin-bottom:16px;">🔔</div>
            <h3>No notifications</h3>
            <p>You're all caught up!</p>
          </div>
        }

        @if (!loading() && notifications().length > 0) {
          <div class="notif-list animate-in">
            @for (n of notifications(); track n.id) {
              <div class="notif-item card" [class.unread]="!n.is_read" (click)="markRead(n)">
                <div class="notif-indicator" [class.visible]="!n.is_read"></div>
                <div class="notif-body">
                  <div class="notif-title">{{ n.title }}</div>
                  <div class="notif-message">{{ n.body }}</div>
                  <div class="notif-meta">
                    <span class="badge badge-primary text-xs">{{ n.notification_type }}</span>
                    <span class="text-muted text-xs">{{ n.created_at | date:'MMM d, y, HH:mm' }}</span>
                  </div>
                </div>
                @if (n.link_url) {
                  <a [href]="n.link_url" class="btn btn-ghost btn-sm" target="_blank">View →</a>
                }
              </div>
            }
          </div>
        }
      </div>
    </div>
  `,
  styles: [`
    .notif-page { background: var(--bg-base); min-height: 100%; }
    .page-header { margin-bottom: 32px; }
    .header-content { display: flex; justify-content: space-between; align-items: center; }
    .notif-list { display: flex; flex-direction: column; gap: 12px; }
    .notif-item {
      display: flex; align-items: flex-start; gap: 16px; padding: 20px;
      cursor: pointer; position: relative;
      &.unread { background: rgba(124,106,247,0.05); border-color: rgba(124,106,247,0.2); }
    }
    .notif-indicator {
      width: 8px; height: 8px; border-radius: 50%; background: var(--primary);
      margin-top: 6px; flex-shrink: 0; opacity: 0;
      &.visible { opacity: 1; }
    }
    .notif-body { flex: 1; }
    .notif-title { font-weight: 600; font-size: 15px; margin-bottom: 6px; }
    .notif-message { color: var(--text-secondary); font-size: 14px; line-height: 1.5; margin-bottom: 10px; }
    .notif-meta { display: flex; align-items: center; gap: 10px; }
    .empty-state { max-width: 360px; margin: 80px auto; }
    .loading-overlay { display: flex; justify-content: center; padding: 80px; }
  `]
})
export class NotificationListComponent implements OnInit {
  private readonly api = inject(ApiService);
  private readonly notifSvc = inject(NotificationService);
  private readonly toast = inject(ToastService);

  readonly loading = signal(true);
  readonly notifications = signal<Notification[]>([]);

  // Computed to avoid arrow functions in template
  readonly hasUnread = computed(() => this.notifications().some(n => !n.is_read));

  ngOnInit(): void {
    this.api.get<Notification[]>(API_ENDPOINTS.NOTIFICATIONS, { limit: 50 }).subscribe({
      next: n => { this.notifications.set(n); this.loading.set(false); },
      error: () => this.loading.set(false),
    });
  }

  markRead(n: Notification): void {
    if (n.is_read) return;
    this.api.post(`${API_ENDPOINTS.NOTIFICATIONS}/${n.id}/read`, {}).subscribe({
      next: () => {
        this.notifications.update(list => list.map(x => x.id === n.id ? { ...x, is_read: true } : x));
        this.notifSvc.refreshCount();
      },
      error: () => {},
    });
  }

  markAllRead(): void {
    this.api.post(API_ENDPOINTS.NOTIFICATIONS_READ_ALL, {}).subscribe({
      next: () => {
        this.notifications.update(list => list.map(n => ({ ...n, is_read: true })));
        this.notifSvc.unreadCount.set(0);
        this.toast.success('All notifications marked as read.');
      },
      error: () => this.toast.error('Failed to mark notifications as read.'),
    });
  }
}
