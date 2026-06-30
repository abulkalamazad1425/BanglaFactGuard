import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';

@Component({
  selector: 'app-footer',
  standalone: true,
  imports: [RouterLink],
  template: `
    <footer class="footer">
      <div class="footer-container">
        <div class="footer-grid">
          <!-- Brand -->
          <div class="footer-brand">
            <div class="brand-logo">
              <svg width="32" height="32" viewBox="0 0 28 28" fill="none">
                <path d="M14 2L24 7.5V20.5L14 26L4 20.5V7.5L14 2Z" fill="url(#fg)" opacity="0.9"/>
                <path d="M10 10.5L14 8L18 10.5V15.5L14 18L10 15.5V10.5Z" fill="white" opacity="0.9"/>
                <defs>
                  <linearGradient id="fg" x1="4" y1="2" x2="24" y2="26" gradientUnits="userSpaceOnUse">
                    <stop stop-color="#7c6af7"/><stop offset="1" stop-color="#a855f7"/>
                  </linearGradient>
                </defs>
              </svg>
              <span>BanglaFactGuard</span>
            </div>
            <p class="brand-tagline">
              AI-powered source-based fact verification for Bangla news using a 12-stage pipeline.
            </p>
            <div class="social-links">
              <a href="https://github.com/abulkalamazad1425/BanglaFactGuard" target="_blank" class="social-link" title="GitHub">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M12 0C5.374 0 0 5.373 0 12c0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23A11.509 11.509 0 0 1 12 5.803c1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576C20.566 21.797 24 17.3 24 12c0-6.627-5.373-12-12-12z"/>
                </svg>
              </a>
            </div>
          </div>

          <!-- Platform -->
          <div class="footer-section">
            <h4>Platform</h4>
            <a routerLink="/verify">Verify a Claim</a>
            <a routerLink="/multimodal">Multimodal Check</a>
            <a routerLink="/dashboard">Public Dashboard</a>
            <a routerLink="/auth/register">Create Account</a>
          </div>

          <!-- Resources -->
          <div class="footer-section">
            <h4>Resources</h4>
            <a href="http://localhost:8000/docs" target="_blank">API Documentation</a>
            <a href="http://localhost:8000/redoc" target="_blank">ReDoc</a>
            <a routerLink="/dashboard">Platform Stats</a>
          </div>

          <!-- Account -->
          <div class="footer-section">
            <h4>Account</h4>
            <a routerLink="/auth/login">Login</a>
            <a routerLink="/auth/register">Register</a>
            <a routerLink="/history">My Submissions</a>
            <a routerLink="/settings">Settings</a>
          </div>
        </div>

        <div class="footer-bottom">
          <p class="copyright">
            &copy; {{ year }} BanglaFactGuard. Built for SPL-3 — BSSE 1425.
          </p>
          <div class="tech-stack">
            <span class="tech-tag">Angular 19</span>
            <span class="tech-tag">FastAPI</span>
            <span class="tech-tag">BanglaBERT</span>
            <span class="tech-tag">EfficientNet-B4</span>
          </div>
        </div>
      </div>
    </footer>
  `,
  styles: [`
    .footer {
      background: var(--bg-surface);
      border-top: 1px solid var(--border);
      margin-top: auto;
    }
    .footer-container {
      max-width: 1280px; margin: 0 auto; padding: 60px 24px 32px;
    }
    .footer-grid {
      display: grid; grid-template-columns: 2fr 1fr 1fr 1fr;
      gap: 48px; margin-bottom: 48px;
      @media (max-width: 900px) { grid-template-columns: 1fr 1fr; gap: 32px; }
      @media (max-width: 480px) { grid-template-columns: 1fr; gap: 24px; }
    }
    .footer-brand {
      .brand-logo {
        display: flex; align-items: center; gap: 10px; margin-bottom: 16px;
        span {
          font-family: var(--font-display); font-size: 18px; font-weight: 700;
          background: var(--gradient-primary);
          -webkit-background-clip: text; background-clip: text;
          -webkit-text-fill-color: transparent;
        }
      }
      .brand-tagline {
        color: var(--text-muted); font-size: 13px; line-height: 1.7;
        max-width: 280px; margin-bottom: 20px;
      }
    }
    .social-links { display: flex; gap: 10px; }
    .social-link {
      width: 36px; height: 36px; border-radius: var(--radius-md);
      background: var(--bg-surface-2); border: 1px solid var(--border);
      display: flex; align-items: center; justify-content: center;
      color: var(--text-muted); text-decoration: none; transition: var(--transition);
      &:hover { color: var(--primary-light); border-color: var(--primary); }
    }
    .footer-section {
      h4 {
        font-size: 13px; font-weight: 600; color: var(--text-primary);
        text-transform: uppercase; letter-spacing: 0.08em;
        margin-bottom: 16px; font-family: var(--font-sans);
      }
      a {
        display: block; font-size: 14px; color: var(--text-muted);
        text-decoration: none; margin-bottom: 10px; transition: var(--transition);
        &:hover { color: var(--primary-light); padding-left: 4px; }
      }
    }
    .footer-bottom {
      display: flex; align-items: center; justify-content: space-between;
      padding-top: 24px; border-top: 1px solid var(--border);
      @media (max-width: 640px) { flex-direction: column; gap: 16px; text-align: center; }
    }
    .copyright { color: var(--text-muted); font-size: 13px; }
    .tech-stack { display: flex; gap: 8px; flex-wrap: wrap; }
    .tech-tag {
      padding: 3px 10px; background: var(--bg-surface-2);
      border: 1px solid var(--border); border-radius: var(--radius-full);
      font-size: 11px; color: var(--text-muted);
    }
  `]
})
export class FooterComponent {
  readonly year = new Date().getFullYear();
}
