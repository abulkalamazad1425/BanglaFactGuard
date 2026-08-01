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
    { icon: '🔎', title: 'Source-Based Verification', desc: 'Submit a headline, body text and a claimed news source. A 12-stage pipeline searches that outlet, retrieves the matching article, and checks it with LaBSE semantic similarity and DeBERTa contradiction detection.' },
    { icon: '🧠', title: 'Multimodal Verification', desc: 'Submit body text with an image. A BanglaBERT + EfficientNet-B4 fusion model analyzes text and image together to flag content as Fake or Non-Fake.' },
    { icon: '⚖️', title: 'Expert Credibility Voting', desc: 'Registered experts review flagged claims — with full access to the AI prediction and evidence — and cast credibility-weighted votes toward a final verdict.' },
    { icon: '📊', title: 'Fact Explorer', desc: 'A public, searchable archive of every verified claim, filterable by keyword, verdict, verification type, source and publication date.' },
    { icon: '🗂️', title: 'Verified Source Registry', desc: 'Administrators curate the list of trusted Bangla news outlets — only active, verified sources are ever eligible for source-based checks.' },
    { icon: '🔔', title: 'Live Notifications', desc: 'Registered users and experts are notified the moment a submitted claim is resolved, or a new claim is assigned for their review.' },
  ];

  readonly verdicts = [
    { label: 'True', icon: '✓', cls: 'badge-true', desc: 'The claimed source actually published this article. High semantic similarity and entity match confirmed.' },
    { label: 'False', icon: '✗', cls: 'badge-false', desc: 'The claimed source did not publish this article, or the content contradicts what was published.' },
    { label: 'Partially True', icon: '◑', cls: 'badge-partial', desc: 'The source published a related article, but key facts have been altered or exaggerated.' },
    { label: 'Not Found', icon: '?', cls: 'badge-not-found', desc: 'No matching article could be located on the claimed source after an exhaustive search.' },
  ];

  ngOnInit(): void {
    this.dashboardSvc.getPublicStats().subscribe({
      next: s => this.stats.set(s),
      error: () => { },
    });
  }
}
