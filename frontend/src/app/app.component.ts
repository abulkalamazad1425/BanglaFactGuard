import { Component, OnInit, inject } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { NotificationService } from './services/notification.service';
import { AuthService } from './services/auth.service';

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
    if (this.auth.user() && localStorage.getItem('bfg_access_token')) {
      this.auth.loadCurrentUser().subscribe({ error: () => {} });
    }
    this.notificationSvc.startPolling();
    this.notificationSvc.refreshCount();
  }
}
