import { Component, OnInit, inject, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { NotificationService } from '../../../services/notification.service';
import { NotificationItem } from '../../../models/notification.model';
import { ToastService } from '../../../shared/services/toast.service';

@Component({
  selector: 'app-notification-list',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './notification-list.html',
  styleUrls: ['./notification-list.scss']
})
export class NotificationListComponent implements OnInit {
  private readonly notifSvc = inject(NotificationService);
  private readonly toast = inject(ToastService);

  readonly loading = signal(true);
  readonly notifications = signal<NotificationItem[]>([]);

  // Computed to avoid arrow functions in template
  readonly hasUnread = computed(() => this.notifications().some(n => !n.is_read));

  ngOnInit(): void {
    this.notifSvc.list(50).subscribe({
      next: n => { this.notifications.set(n); this.loading.set(false); },
      error: () => this.loading.set(false),
    });
  }

  markRead(n: NotificationItem): void {
    if (n.is_read) return;
    this.notifSvc.markRead(n.id).subscribe({
      next: () => {
        this.notifications.update(list => list.map(x => x.id === n.id ? { ...x, is_read: true } : x));
        this.notifSvc.refreshCount();
      },
      error: () => { },
    });
  }

  markAllRead(): void {
    this.notifSvc.markAllRead().subscribe({
      next: () => {
        this.notifications.update(list => list.map(n => ({ ...n, is_read: true })));
        this.toast.success('All notifications marked as read.');
      },
      error: () => this.toast.error('Failed to mark notifications as read.'),
    });
  }
}
