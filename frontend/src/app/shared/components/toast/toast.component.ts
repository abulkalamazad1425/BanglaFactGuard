import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Toast, ToastService } from '../../services/toast.service';

@Component({
  selector: 'app-toast',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="toast-container">
      @for (toast of toastSvc.toasts(); track toast.id) {
        <div class="toast toast--{{ toast.type }}" (click)="dismiss(toast)">
          <span class="toast-icon">{{ icons[toast.type] }}</span>
          <span class="toast-message">{{ toast.message }}</span>
          <button class="toast-close" (click)="dismiss(toast)">✕</button>
        </div>
      }
    </div>
  `,
  styles: [`
    .toast-container {
      position: fixed; bottom: 24px; right: 24px; z-index: 9999;
      display: flex; flex-direction: column; gap: 10px;
      max-width: 380px; width: 100%;
    }
    .toast {
      display: flex; align-items: center; gap: 12px;
      padding: 14px 16px; border-radius: var(--radius-md);
      background: var(--bg-elevated); border: 1px solid var(--border);
      box-shadow: var(--shadow-lg); cursor: pointer;
      animation: fadeIn 0.3s ease;

      &--success { border-color: rgba(34,197,94,0.3); }
      &--error   { border-color: rgba(239,68,68,0.3); }
      &--warning { border-color: rgba(245,158,11,0.3); }
      &--info    { border-color: rgba(59,130,246,0.3); }
    }
    .toast-icon { font-size: 16px; flex-shrink: 0; }
    .toast-message { flex: 1; font-size: 14px; color: var(--text-primary); }
    .toast-close {
      background: none; border: none; cursor: pointer;
      color: var(--text-muted); font-size: 14px; padding: 2px;
      &:hover { color: var(--text-primary); }
    }
  `]
})
export class ToastComponent {
  readonly toastSvc = inject(ToastService);

  readonly icons: Record<string, string> = {
    success: '✅', error: '❌', warning: '⚠️', info: 'ℹ️',
  };

  dismiss(toast: Toast): void {
    this.toastSvc.dismiss(toast.id);
  }
}
