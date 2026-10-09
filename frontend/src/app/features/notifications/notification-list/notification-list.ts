import { readableExplanation } from '../../../shared/utils/presentation';
import { Component, OnInit, OnDestroy, inject, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { NotificationService } from '../../../services/notification.service';
import { NotificationItem } from '../../../models/notification.model';
import { ToastService } from '../../../shared/services/toast.service';
import {
  PAGE_SIZE,
  PaginationComponent,
} from '../../../shared/components/pagination/pagination.component';

@Component({
  selector: 'app-notification-list',
  standalone: true,
  imports: [CommonModule, RouterLink, PaginationComponent],
  templateUrl: './notification-list.html',
  styleUrls: ['./notification-list.scss'],
})
export class NotificationListComponent implements OnInit, OnDestroy {
  readonly readableExplanation = readableExplanation;
  private readonly notifSvc = inject(NotificationService);
  private readonly toast = inject(ToastService);

  readonly loading = signal(true);
  readonly loadError = signal(false);
  readonly notifications = signal<NotificationItem[]>([]);
  readonly page = signal(1);
  readonly hasNext = signal(false);
  readonly limit = PAGE_SIZE;

  // Computed to avoid arrow functions in template. Unread items may sit on
  // another page, so the server-wide unread count counts too.
  readonly hasUnread = computed(
    () => this.notifSvc.unreadCount() > 0 || this.notifications().some((n) => !n.is_read),
  );

  private timer?: ReturnType<typeof setInterval>;
  ngOnInit(): void {
    this.load();
    this.timer ??= setInterval(() => {
      if (!document.hidden) this.load();
    }, 15000);
  }
  ngOnDestroy(): void {
    if (this.timer) clearInterval(this.timer);
  }
  load(): void {
    // One extra row tells whether another page exists.
    this.notifSvc.list(this.limit + 1, (this.page() - 1) * this.limit).subscribe({
      next: (rows) => {
        this.hasNext.set(rows.length > this.limit);
        this.notifications.set(rows.slice(0, this.limit));
        this.loading.set(false);
        this.loadError.set(false);
      },
      error: () => {
        this.loading.set(false);
        this.loadError.set(true);
      },
    });
  }

  goToPage(page: number): void {
    this.page.set(page);
    this.loading.set(true);
    this.load();
  }

  /** These notifications carry the claim headline's first words — shown as written. */
  isHeadlinePreview(n: NotificationItem): boolean {
    return ['VERIFICATION_COMPLETE', 'EXPERT_REVIEW_COMPLETE', 'CLAIM_ESCALATED'].includes(
      n.notification_type,
    );
  }

  typeLabel(type: string): string {
    return (
      (
        {
          VERIFICATION_COMPLETE: 'Preliminary result',
          EXPERT_REVIEW_COMPLETE: 'Final decision',
          CLAIM_ESCALATED: 'Escalated claim',
          VERIFICATION_FAILED: 'Check incomplete',
        } as Record<string, string>
      )[type] ?? 'Update'
    );
  }

  markRead(n: NotificationItem): void {
    if (n.is_read) return;
    this.notifSvc.markRead(n.id).subscribe({
      next: () => {
        this.notifications.update((list) =>
          list.map((x) => (x.id === n.id ? { ...x, is_read: true } : x)),
        );
        this.notifSvc.refreshCount();
      },
      error: () => {},
    });
  }

  markAllRead(): void {
    this.notifSvc.markAllRead().subscribe({
      next: () => {
        this.notifications.update((list) => list.map((n) => ({ ...n, is_read: true })));
        this.toast.success('All notifications marked as read.');
      },
      error: () => this.toast.error('Failed to mark notifications as read.'),
    });
  }
}
