import { Component, OnInit, inject } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { NotificationService } from './core/services/notification.service';
import { AuthService } from './core/services/auth.service';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet],
  template: `<router-outlet />`,
})
export class AppComponent implements OnInit {
  private readonly notificationSvc = inject(NotificationService);
  private readonly auth = inject(AuthService);

  ngOnInit(): void {
    // Load current user if tokens are present
    if (this.auth.user() && localStorage.getItem('bfg_access_token')) {
      this.auth.loadCurrentUser().subscribe({ error: () => {} });
    }
    // Start notification polling
    this.notificationSvc.startPolling();
    // Initial count fetch if logged in
    this.notificationSvc.refreshCount();
  }
}
