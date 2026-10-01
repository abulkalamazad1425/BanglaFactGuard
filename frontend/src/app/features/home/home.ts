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
    { icon: '🖼️', title: 'Photo Card Verification', desc: 'Upload a Bangla photo card or screenshot. OCR reads the Bangla text, card chrome and branding are stripped away, the claimed outlet is detected automatically — then you confirm the claim before it is checked against that source.' },
    { icon: '⚖️', title: 'Expert Credibility Voting', desc: 'Registered experts review flagged claims — with full access to the AI prediction and evidence — and cast credibility-weighted votes toward a final verdict.' },
    { icon: '📊', title: 'Fact Explorer', desc: 'A public, searchable archive of every verified claim, filterable by keyword, verdict, verification type, source and publication date.' },
    { icon: '🗂️', title: 'Verified Source Registry', desc: 'Administrators curate the list of trusted Bangla news outlets — only active, verified sources are ever eligible for source-based checks.' },
    { icon: '🔔', title: 'Live Notifications', desc: 'Registered users and experts are notified the moment a submitted claim is resolved, or a new claim is assigned for their review.' },
  ];

  readonly verdicts = [
    { label: 'Source Confirmed', icon: '✓', cls: 'badge-true', desc: 'The claimed source actually published a matching story. Checked independently of content or date.' },
    { label: 'Source Not Found', icon: '?', cls: 'badge-not-found', desc: 'No matching article could be located on the claimed source after an exhaustive search.' },
    { label: 'Content Matched', icon: '✓', cls: 'badge-true', desc: 'Once the source is confirmed, the claimed content carries the same facts — paraphrase and reordering included.' },
    { label: 'Content Altered', icon: '◑', cls: 'badge-partial', desc: 'Material facts changed, or the claim contradicts what the source actually published.' },
    { label: 'Date Matched / Mismatched', icon: '📅', cls: 'badge-partial', desc: 'Whether the claimed publication date matches the source’s actual date — informational only, never a verdict on the content.' },
  ];

  ngOnInit(): void {
    this.dashboardSvc.getPublicStats().subscribe({
      next: s => this.stats.set(s),
      error: () => { },
    });
  }
}
