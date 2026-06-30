import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';

@Component({
  selector: 'app-not-found',
  standalone: true,
  imports: [RouterLink],
  template: `
    <div class="nf-page">
      <div class="nf-content animate-scale">
        <div class="nf-code gradient-text">404</div>
        <h1>Page Not Found</h1>
        <p>The page you're looking for doesn't exist or has been moved.</p>
        <div class="nf-actions">
          <a routerLink="/" class="btn btn-primary btn-lg">Go Home</a>
          <a routerLink="/verify" class="btn btn-secondary btn-lg">Verify a Claim</a>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .nf-page {
      min-height: 100%; display: flex; align-items: center; justify-content: center;
      padding: 80px 24px; text-align: center;
    }
    .nf-code {
      font-size: clamp(6rem, 15vw, 10rem); font-weight: 900;
      font-family: var(--font-display); line-height: 1;
      margin-bottom: 24px; letter-spacing: -0.05em;
    }
    h1 { margin-bottom: 16px; }
    p { color: var(--text-secondary); margin-bottom: 40px; font-size: 16px; }
    .nf-actions { display: flex; gap: 16px; justify-content: center; flex-wrap: wrap; }
  `]
})
export class NotFoundComponent {}
