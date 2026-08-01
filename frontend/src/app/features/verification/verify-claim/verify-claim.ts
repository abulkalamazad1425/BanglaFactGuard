import { Component, OnInit, inject } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router } from '@angular/router';
import { CommonModule } from '@angular/common';
import { ToastService } from '../../../shared/services/toast.service';
import { VerificationService } from '../../../services/verification.service';
import { VerificationResponse } from '../../../models/verification.model';
import { SourceService } from '../../../services/source.service';
import { SourceResponse } from '../../../models/source.model';


@Component({
  selector: 'app-verify-claim',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule],
  templateUrl: './verify-claim.html',
  styleUrls: ['./verify-claim.scss'],
})
export class VerifyClaimComponent implements OnInit {
  private readonly fb = inject(FormBuilder);
  private readonly router = inject(Router);
  private readonly toast = inject(ToastService);
  private readonly svc = inject(VerificationService);
  private readonly sourceSvc = inject(SourceService);

  loading = false;
  error: string | null = null;
  result: VerificationResponse | null = null;

  sources: SourceResponse[] = [];
  sourcesLoading = true;

  form = this.fb.group({
    headline: ['', [Validators.required, Validators.minLength(10)]],
    claimed_source: ['', [Validators.required]],
    news_body: [''],
    published_date: [''],
    force_refresh: [false],
  });

  ngOnInit(): void {
    // Only active verified sources are ever eligible for selection here.
    this.sourceSvc.listSources(undefined, 1, 100).subscribe({
      next: (res) => {
        this.sources = [...res.items].sort((a, b) => a.display_name.localeCompare(b.display_name, 'bn'));
        this.sourcesLoading = false;
      },
      error: () => { this.sourcesLoading = false; },
    });
  }

  get headlineInvalid() {
    return this.form.get('headline')?.invalid && this.form.get('headline')?.touched;
  }

  get sourceInvalid() {
    return this.form.get('claimed_source')?.invalid && this.form.get('claimed_source')?.touched;
  }

  onSubmit(): void {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }

    this.loading = true;
    this.error = null;
    this.result = null;

    const v = this.form.value;
    const payload: any = {
      headline: v.headline,
      claimed_source: v.claimed_source,
      force_refresh: v.force_refresh ?? false,
    };
    if (v.news_body?.trim()) payload.news_body = v.news_body;
    if (v.published_date) payload.published_date = v.published_date;

    this.svc.submit(payload).subscribe({
      next: (res) => {
        this.loading = false;
        this.svc.getResult(res.claim_id).subscribe({
          next: (result) => { this.result = result; },
          error: () => { this.toast.error('Failed to load result.'); },
        });
      },
      error: (err) => {
        this.loading = false;
        this.error = err.error?.detail?.message
          || err.error?.message
          || 'Failed to connect to backend engine. Ensure the API server is running on port 8000.';
        this.toast.error(this.error!);
      },
    });
  }

  reset(): void {
    this.error = null;
    this.result = null;
  }

  /* ─── Template helpers ─── */

  verdictColor(label: string): string {
    const map: Record<string, string> = {
      TRUE: '#10b981',
      FALSE: '#ef4444',
      PARTIALLY_TRUE: '#f59e0b',
      NOT_FOUND_IN_CLAIMED_SOURCE: '#6b7280',
    };
    return map[label] ?? '#6b7280';
  }

  getBadgeClass(label: string): string {
    switch (label?.toUpperCase()) {
      case 'TRUE': return 'true';
      case 'FALSE': return 'false';
      case 'PARTIALLY_TRUE': return 'partial';
      default: return 'notfound';
    }
  }

  getBadgeIcon(label: string): string {
    switch (label?.toUpperCase()) {
      case 'TRUE': return '✓';
      case 'FALSE': return '✗';
      case 'PARTIALLY_TRUE': return '⚠';
      default: return '?';
    }
  }

  formatVerdict(label: string): string {
    if (!label) return '';
    return label.replace(/_/g, ' ');
  }

  getDashOffset(confidence: number): number {
    // Circumference of r=45 circle ≈ 282.7
    return 283 - 283 * (confidence || 0);
  }

  getHost(url: string): string {
    try {
      return new URL(url).hostname.replace('www.', '');
    } catch {
      return '';
    }
  }
}
