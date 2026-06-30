import { Component } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { NavbarComponent } from '../../shared/components/navbar/navbar.component';
import { FooterComponent } from '../../shared/components/footer/footer.component';
import { ToastComponent } from '../../shared/components/toast/toast.component';

@Component({
  selector: 'app-main-layout',
  standalone: true,
  imports: [RouterOutlet, NavbarComponent, FooterComponent, ToastComponent],
  template: `
    <div class="app-shell">
      <app-navbar />
      <main class="main-content">
        <router-outlet />
      </main>
      <app-footer />
      <app-toast />
    </div>
  `,
  styles: [`
    .app-shell {
      display: flex; flex-direction: column; min-height: 100vh;
    }
    .main-content {
      flex: 1; padding-top: 64px; /* navbar height */
    }
  `]
})
export class MainLayoutComponent {}
