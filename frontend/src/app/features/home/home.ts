import { Component, OnInit, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { CommonModule } from '@angular/common';
import { DashboardService } from '../../services/dashboard.service';
import { AuthService } from '../../services/auth.service';
import { PublicStats } from '../../models/admin.model';

@Component({
  selector: 'app-home',
  standalone: true,
  imports: [CommonModule, RouterLink],
  templateUrl: './home.html',
  styleUrls: ['./home.scss']
})
export class HomeComponent implements OnInit {
  private readonly dashboardSvc = inject(DashboardService);
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
    this.dashboardSvc.getPublicStats().subscribe({
      next: s => this.stats.set(s),
      error: () => { },
    });
  }
}
