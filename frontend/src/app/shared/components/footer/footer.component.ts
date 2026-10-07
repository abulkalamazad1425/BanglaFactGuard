import { Component, inject } from '@angular/core';
import { RouterLink } from '@angular/router';
import { AuthService } from '../../../services/auth.service';
import { VERIFY_OPTIONS } from '../../../features/verification/verify-facts/verify-options';

@Component({
  selector: 'app-footer',
  standalone: true,
  imports: [RouterLink],
  template: `
    <footer class="footer">
      <div class="footer-container">
        <div class="footer-grid">
          <div class="footer-brand">
            <a routerLink="/" class="brand-logo">
              <svg width="32" height="32" viewBox="0 0 28 28" fill="none" aria-hidden="true">
                <path d="M14 2L24 7.5V20.5L14 26L4 20.5V7.5L14 2Z" fill="url(#fg)" opacity="0.9"/>
                <path d="M10 10.5L14 8L18 10.5V15.5L14 18L10 15.5V10.5Z" fill="white" opacity="0.9"/>
                <defs>
                  <linearGradient id="fg" x1="4" y1="2" x2="24" y2="26" gradientUnits="userSpaceOnUse">
                    <stop stop-color="#1f7f4e"/><stop offset="1" stop-color="#186640"/>
                  </linearGradient>
                </defs>
              </svg>
              <span>BanglaFactGuard</span>
            </a>
            <p class="brand-tagline">Fact checking for Bangla news, images and photocards — automated first results, expert-reviewed final verdicts.</p>
            <a routerLink="/verify" class="btn btn-primary btn-sm">Verify facts ↗</a>
          </div>

          <nav class="footer-section" aria-label="Verify facts">
            <h4>Verify facts</h4>
            @for (opt of options; track opt.key) {
              <a routerLink="/verify" [queryParams]="{ method: opt.key }">{{ opt.title }}</a>
            }
          </nav>

          <nav class="footer-section" aria-label="Explore">
            <h4>Explore</h4>
            <a routerLink="/dashboard">Fact Explorer</a>
            <a routerLink="/about">About</a>
            <a routerLink="/faq">FAQ</a>
          </nav>

          <nav class="footer-section" aria-label="Account">
            <h4>Account</h4>
            @if (isLoggedIn()) {
              <a routerLink="/history">My Submissions</a>
              <a routerLink="/notifications">Notifications</a>
              <a routerLink="/settings">Account settings</a>
            } @else {
              <a routerLink="/auth/login">Login</a>
              <a routerLink="/auth/register">Create account</a>
            }
          </nav>
        </div>

        <p class="footer-disclaimer">
          Initial results are produced automatically and can be wrong. Only expert-reviewed verdicts are final. Always check the evidence before sharing.
        </p>

        <div class="footer-bottom">
          <p>&copy; {{ year }} BanglaFactGuard</p>
          <div class="bottom-links">
            <a routerLink="/about">About</a>
            <a routerLink="/faq">FAQ</a>
            <a href="https://github.com/abulkalamazad1425/BanglaFactGuard" target="_blank" rel="noopener" class="gh-link" aria-label="GitHub">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                <path d="M12 0C5.374 0 0 5.373 0 12c0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23A11.509 11.509 0 0 1 12 5.803c1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576C20.566 21.797 24 17.3 24 12c0-6.627-5.373-12-12-12z"/>
              </svg>
              GitHub
            </a>
          </div>
        </div>
      </div>
    </footer>
  `,
  styles: [`
    .footer { background: var(--bg-surface); border-top: 1px solid var(--border); margin-top: auto; }
    .footer-container { max-width: 1280px; margin: 0 auto; padding: 56px 24px 28px; }
    .footer-grid {
      display: grid; grid-template-columns: 1.6fr 1.2fr 1fr 1fr; gap: 40px; margin-bottom: 36px;
      @media (max-width: 900px) { grid-template-columns: 1fr 1fr; gap: 32px; }
      @media (max-width: 480px) { grid-template-columns: 1fr; gap: 26px; }
    }
    .brand-logo {
      display: inline-flex; align-items: center; gap: 10px; margin-bottom: 14px; text-decoration: none;
      span {
        font-family: var(--font-display); font-size: 18px; font-weight: 700;
        background: var(--gradient-primary); -webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent;
      }
    }
    .brand-tagline { color: var(--text-muted); font-size: 13.5px; line-height: 1.7; max-width: 300px; margin: 0 0 18px; }
    .footer-section {
      display: flex; flex-direction: column; gap: 10px;
      h4 { font-size: 12px; font-weight: 650; color: var(--text-primary); text-transform: uppercase; letter-spacing: .08em; margin: 0 0 6px; font-family: var(--font-sans); }
      a { font-size: 14px; color: var(--text-muted); text-decoration: none; transition: color .15s; &:hover { color: var(--primary-light); } }
    }
    .footer-disclaimer {
      margin: 0 0 22px; padding: 14px 16px; border-radius: 10px; background: var(--bg-surface-2);
      font-size: 12.5px; line-height: 1.7; color: var(--text-secondary);
    }
    .footer-bottom {
      display: flex; align-items: center; justify-content: space-between; gap: 16px; flex-wrap: wrap;
      padding-top: 20px; border-top: 1px solid var(--border); font-size: 13px; color: var(--text-muted);
      p { margin: 0; }
    }
    .bottom-links { display: flex; align-items: center; gap: 20px;
      a { color: var(--text-muted); text-decoration: none; &:hover { color: var(--primary-light); } }
    }
    .gh-link { display: inline-flex; align-items: center; gap: 6px; }
  `]
})
export class FooterComponent {
  readonly year = new Date().getFullYear();
  readonly options = VERIFY_OPTIONS;
  readonly isLoggedIn = inject(AuthService).isLoggedIn;
}
