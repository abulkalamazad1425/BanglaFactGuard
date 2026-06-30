import { Component, OnInit, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { CommonModule } from '@angular/common';
import { ApiService } from '../../core/services/api.service';
import { AuthService } from '../../core/services/auth.service';
import { PublicStats } from '../../core/models/admin.model';
import { API_ENDPOINTS } from '../../core/constants/api-endpoints.constant';

@Component({
  selector: 'app-home',
  standalone: true,
  imports: [CommonModule, RouterLink],
  template: `
    <div class="home">
      <!-- Hero -->
      <section class="hero">
        <div class="hero-bg">
          <div class="hero-blob hero-blob-1"></div>
          <div class="hero-blob hero-blob-2"></div>
          <div class="hero-grid"></div>
        </div>
        <div class="container hero-content animate-in">
          <div class="hero-badge">
            <span class="badge badge-primary">🔬 AI-Powered Fact Verification</span>
          </div>
          <h1 class="hero-title">
            Verify Bangla News<br>
            <span class="gradient-text">With Confidence</span>
          </h1>
          <p class="hero-subtitle">
            BanglaFactGuard uses a 12-stage AI pipeline combining BanglaBERT, EfficientNet, semantic search,
            and expert review to verify Bangla news claims against their claimed sources.
          </p>
          <div class="hero-actions">
            <a routerLink="/verify" class="btn btn-primary btn-lg">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
              Verify a Claim
            </a>
            <a routerLink="/multimodal" class="btn btn-secondary btn-lg">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M9 9h.01M15 9h.01M9 15h.01M15 15h.01M12 12h.01"/></svg>
              Multimodal Check
            </a>
          </div>

          <!-- Stats bar -->
          @if (stats()) {
            <div class="hero-stats animate-in">
              <div class="stat-item">
                <span class="stat-num">{{ stats()!.total_submissions | number }}</span>
                <span class="stat-lbl">Total Claims</span>
              </div>
              <div class="stat-divider"></div>
              <div class="stat-item">
                <span class="stat-num text-success">{{ stats()!.true_count | number }}</span>
                <span class="stat-lbl">Verified True</span>
              </div>
              <div class="stat-divider"></div>
              <div class="stat-item">
                <span class="stat-num text-error">{{ stats()!.false_count | number }}</span>
                <span class="stat-lbl">Found False</span>
              </div>
              <div class="stat-divider"></div>
              <div class="stat-item">
                <span class="stat-num text-warning">{{ stats()!.partially_true_count | number }}</span>
                <span class="stat-lbl">Partially True</span>
              </div>
            </div>
          }
        </div>
      </section>

      <!-- Features -->
      <section class="section features">
        <div class="container">
          <div class="section-header">
            <h2>How It Works</h2>
            <p>A comprehensive 12-stage pipeline for accurate fact verification</p>
          </div>
          <div class="grid-3">
            @for (feat of features; track feat.icon) {
              <div class="feature-card glass-card">
                <div class="feature-icon">{{ feat.icon }}</div>
                <h3>{{ feat.title }}</h3>
                <p>{{ feat.desc }}</p>
              </div>
            }
          </div>
        </div>
      </section>

      <!-- Verdict Types -->
      <section class="section section-sm verdicts">
        <div class="container">
          <div class="section-header">
            <h2>Verdict Types</h2>
            <p>BanglaFactGuard returns one of four possible verdicts</p>
          </div>
          <div class="grid-2">
            @for (v of verdicts; track v.label) {
              <div class="verdict-card card">
                <div class="verdict-badge" [ngClass]="v.cls">{{ v.icon }} {{ v.label }}</div>
                <p>{{ v.desc }}</p>
              </div>
            }
          </div>
        </div>
      </section>

      <!-- CTA -->
      <section class="section section-sm cta">
        <div class="container container-sm">
          <div class="cta-card glass-card">
            <h2>Ready to fact-check?</h2>
            <p>Submit your first claim and get a detailed AI analysis in seconds.</p>
            <div class="cta-actions">
              <a routerLink="/verify" class="btn btn-primary btn-lg">Start Verifying</a>
              @if (!isLoggedIn()) {
                <a routerLink="/auth/register" class="btn btn-ghost btn-lg">Create Free Account</a>
              }
            </div>
          </div>
        </div>
      </section>
    </div>
  `,
  styles: [`
    .home { overflow-x: hidden; }

    /* Hero */
    .hero {
      position: relative; padding: 120px 0 80px; overflow: hidden;
      min-height: 80vh; display: flex; align-items: center;
    }
    .hero-bg { position: absolute; inset: 0; pointer-events: none; }
    .hero-blob {
      position: absolute; border-radius: 50%; filter: blur(100px); opacity: 0.12;
      &-1 { width: 800px; height: 800px; top: -300px; right: -200px; background: radial-gradient(#7c6af7, #a855f7); }
      &-2 { width: 600px; height: 600px; bottom: -200px; left: -100px; background: radial-gradient(#a855f7, #ec4899); }
    }
    .hero-grid {
      position: absolute; inset: 0;
      background-image: linear-gradient(rgba(124,106,247,0.04) 1px, transparent 1px),
                        linear-gradient(90deg, rgba(124,106,247,0.04) 1px, transparent 1px);
      background-size: 48px 48px;
    }
    .hero-content { position: relative; z-index: 1; text-align: center; padding: 0 24px; }
    .hero-badge { margin-bottom: 24px; }
    .hero-title { font-size: clamp(2.5rem, 6vw, 4rem); margin-bottom: 24px; line-height: 1.15; }
    .hero-subtitle { font-size: 18px; color: var(--text-secondary); max-width: 640px; margin: 0 auto 40px; }
    .hero-actions { display: flex; gap: 16px; justify-content: center; flex-wrap: wrap; }
    .hero-stats {
      display: flex; align-items: center; justify-content: center; gap: 32px;
      margin-top: 56px; padding: 24px 32px; border-radius: var(--radius-xl);
      background: rgba(255,255,255,0.03); border: 1px solid var(--border);
      backdrop-filter: blur(10px); flex-wrap: wrap; gap: 16px;
    }
    .stat-item { text-align: center; }
    .stat-num { display: block; font-size: 2rem; font-weight: 800; font-family: var(--font-display); }
    .stat-lbl { font-size: 12px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; }
    .stat-divider { width: 1px; height: 40px; background: var(--border); }

    /* Features */
    .section-header { text-align: center; margin-bottom: 48px;
      h2 { margin-bottom: 12px; }
      p { color: var(--text-secondary); font-size: 16px; }
    }
    .feature-card { text-align: center; }
    .feature-icon { font-size: 40px; margin-bottom: 16px; }
    .feature-card h3 { font-size: 1.1rem; margin-bottom: 10px; }
    .feature-card p { color: var(--text-secondary); font-size: 14px; }

    /* Verdicts */
    .verdict-card { display: flex; flex-direction: column; gap: 12px; }
    .verdict-badge { display: inline-flex; align-items: center; gap: 6px; padding: 6px 14px; border-radius: var(--radius-full); font-size: 14px; font-weight: 600; align-self: flex-start; }

    /* CTA */
    .cta-card { text-align: center; h2 { margin-bottom: 12px; } p { margin-bottom: 32px; } }
    .cta-actions { display: flex; gap: 16px; justify-content: center; flex-wrap: wrap; }
  `]
})
export class HomeComponent implements OnInit {
  private readonly api = inject(ApiService);
  readonly auth = inject(AuthService);

  readonly stats = signal<PublicStats | null>(null);
  readonly isLoggedIn = this.auth.isLoggedIn;

  readonly features = [
    { icon: '🔍', title: 'Source Search', desc: 'Multi-provider search across NewsData.io, Google CSE, and PyGoogleNews to find evidence articles.' },
    { icon: '🧠', title: 'NLP Analysis', desc: 'BanglaBERT-powered semantic similarity, NER entity matching, and DeBERTa NLI contradiction detection.' },
    { icon: '👁️', title: 'Multimodal Check', desc: 'EfficientNet-B4 + BanglaBERT fusion model for detecting fake news from image-text pairs.' },
    { icon: '⚖️', title: 'Expert Review', desc: 'Credibility-weighted expert panel review system that refines AI predictions.' },
    { icon: '📊', title: '12-Stage Pipeline', desc: 'Sequential verification stages from claim normalization to weighted verdict finalization.' },
    { icon: '🔒', title: 'Secure & Private', desc: 'JWT authentication, refresh token rotation, bcrypt hashing, and RBAC role system.' },
  ];

  readonly verdicts = [
    { label: 'True', icon: '✓', cls: 'badge-true', desc: 'The claimed source actually published this article. High semantic similarity and entity match confirmed.' },
    { label: 'False', icon: '✗', cls: 'badge-false', desc: 'The claimed source did not publish this article, or the content contradicts what was published.' },
    { label: 'Partially True', icon: '◑', cls: 'badge-partial', desc: 'The source published a related article, but key facts have been altered or exaggerated.' },
    { label: 'Not Found', icon: '?', cls: 'badge-not-found', desc: 'No relevant evidence was found in the claimed source or any related news outlets.' },
  ];

  ngOnInit(): void {
    this.api.get<PublicStats>(API_ENDPOINTS.DASHBOARD_STATS).subscribe({
      next: s => this.stats.set(s),
      error: () => {},
    });
  }
}
