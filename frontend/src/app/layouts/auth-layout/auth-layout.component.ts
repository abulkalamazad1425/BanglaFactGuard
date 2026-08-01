import { Component } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { ToastComponent } from '../../shared/components/toast/toast.component';
import { RouterLink } from '@angular/router';

@Component({
  selector: 'app-auth-layout',
  standalone: true,
  imports: [RouterOutlet, ToastComponent, RouterLink],
  template: `
    <div class="auth-shell">
      <!-- Background decoration -->
      <div class="auth-bg">
        <div class="bg-blob bg-blob-1"></div>
        <div class="bg-blob bg-blob-2"></div>
        <div class="bg-grid"></div>
      </div>

      <!-- Auth card -->
      <div class="auth-wrapper">
        <a routerLink="/" class="auth-brand">
          <svg width="32" height="32" viewBox="0 0 28 28" fill="none">
            <path d="M14 2L24 7.5V20.5L14 26L4 20.5V7.5L14 2Z" fill="url(#ag)" opacity="0.9"/>
            <path d="M10 10.5L14 8L18 10.5V15.5L14 18L10 15.5V10.5Z" fill="white" opacity="0.9"/>
            <defs>
              <linearGradient id="ag" x1="4" y1="2" x2="24" y2="26" gradientUnits="userSpaceOnUse">
                <stop stop-color="#5b3df0"/><stop offset="1" stop-color="#9333ea"/>
              </linearGradient>
            </defs>
          </svg>
          <span>BanglaFactGuard</span>
        </a>
        <router-outlet />
      </div>

      <app-toast />
    </div>
  `,
  styles: [`
    .auth-shell {
      min-height: 100vh; display: flex; align-items: center;
      justify-content: center; padding: 24px; position: relative; overflow: hidden;
      background: var(--bg-base);
    }
    .auth-bg { position: fixed; inset: 0; z-index: 0; pointer-events: none; }
    .bg-blob {
      position: absolute; border-radius: 50%;
      filter: blur(90px); opacity: 0.16;
      &-1 {
        width: 600px; height: 600px; top: -200px; right: -100px;
        background: radial-gradient(circle, #5b3df0, #9333ea);
      }
      &-2 {
        width: 500px; height: 500px; bottom: -200px; left: -100px;
        background: radial-gradient(circle, #9333ea, #db2777);
      }
    }
    .bg-grid {
      position: absolute; inset: 0;
      background-image: linear-gradient(rgba(91,61,240,0.06) 1px, transparent 1px),
                        linear-gradient(90deg, rgba(91,61,240,0.06) 1px, transparent 1px);
      background-size: 40px 40px;
    }
    .auth-wrapper {
      position: relative; z-index: 1;
      width: 100%; max-width: 460px;
      display: flex; flex-direction: column; align-items: center; gap: 32px;
    }
    .auth-brand {
      display: flex; align-items: center; gap: 10px; text-decoration: none;
      span {
        font-family: var(--font-display); font-size: 20px; font-weight: 700;
        background: var(--gradient-primary);
        -webkit-background-clip: text; background-clip: text;
        -webkit-text-fill-color: transparent;
      }
    }
  `]
})
export class AuthLayoutComponent {}
