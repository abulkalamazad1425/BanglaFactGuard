import { Component } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { ToastComponent } from '../../shared/components/toast/toast.component';
import { RouterLink } from '@angular/router';
import { NavbarComponent } from '../../shared/components/navbar/navbar.component';
import { FooterComponent } from '../../shared/components/footer/footer.component';

@Component({
  selector: 'app-auth-layout',
  standalone: true,
  imports: [RouterOutlet, ToastComponent, RouterLink, NavbarComponent, FooterComponent],
  // Same outer shell as the main layout (skip link, navbar, footer, one
  // toast host) around the centred auth card.
  template: `
    <a class="skip-link" href="#main-content">Skip to content</a>
    <app-navbar />
    <main class="auth-shell" id="main-content" tabindex="-1">
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
            <path d="M14 2L24 7.5V20.5L14 26L4 20.5V7.5L14 2Z" fill="url(#ag)" opacity="0.9" />
            <path d="M10 10.5L14 8L18 10.5V15.5L14 18L10 15.5V10.5Z" fill="white" opacity="0.9" />
            <defs>
              <linearGradient id="ag" x1="4" y1="2" x2="24" y2="26" gradientUnits="userSpaceOnUse">
                <stop stop-color="#1f7f4e" />
                <stop offset="1" stop-color="#186640" />
              </linearGradient>
            </defs>
          </svg>
          <span>BanglaFactGuard</span>
        </a>
        <router-outlet />
      </div>
    </main>
    <app-footer />
    <app-toast />
  `,
  styles: [
    `
      :host {
        display: flex;
        flex-direction: column;
        min-height: 100vh;
      }
      .auth-shell {
        flex: 1;
        min-height: calc(100vh - 64px);
        display: flex;
        align-items: center;
        justify-content: center;
        /* the fixed navbar is 64px tall */
        padding: calc(64px + 24px) 24px 24px;
        position: relative;
        overflow: hidden;
        background: var(--bg-base);
      }
      .auth-bg {
        position: fixed;
        inset: 0;
        z-index: 0;
        pointer-events: none;
      }
      .bg-blob {
        position: absolute;
        border-radius: 50%;
        filter: blur(90px);
        opacity: 0.16;
        &-1 {
          width: 600px;
          height: 600px;
          top: -200px;
          right: -100px;
          background: radial-gradient(circle, #1f7f4e, #186640);
        }
        &-2 {
          width: 500px;
          height: 500px;
          bottom: -200px;
          left: -100px;
          background: radial-gradient(circle, #186640, #435c54);
        }
      }
      .bg-grid {
        position: absolute;
        inset: 0;
        background-image:
          linear-gradient(rgba(31, 127, 78, 0.06) 1px, transparent 1px),
          linear-gradient(90deg, rgba(31, 127, 78, 0.06) 1px, transparent 1px);
        background-size: 40px 40px;
      }
      .auth-wrapper {
        position: relative;
        z-index: 1;
        width: 100%;
        max-width: 460px;
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 32px;
      }
      .auth-brand {
        display: flex;
        align-items: center;
        gap: 10px;
        text-decoration: none;
        span {
          font-family: var(--font-display);
          font-size: 20px;
          font-weight: 700;
          background: var(--gradient-primary);
          -webkit-background-clip: text;
          background-clip: text;
          -webkit-text-fill-color: transparent;
        }
      }
    `,
  ],
})
export class AuthLayoutComponent {}
