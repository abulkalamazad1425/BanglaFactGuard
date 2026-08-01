import { Component, OnInit, inject, signal, computed } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { CommonModule } from '@angular/common';
import { ExpertService } from '../../../services/expert.service';
import { ToastService } from '../../../shared/services/toast.service';
import { ExpertQueueItem } from '../../../models/expert.model';
import { VerificationResponse, MatchedArticle } from '../../../models/verification.model';
import { VerdictBadgeComponent } from '../../../shared/components/verdict-badge/verdict-badge.component';
import { ScoreBarComponent } from '../../../shared/components/score-bar/score-bar.component';
import { VerificationService } from '../../../services/verification.service';
import { AuthService } from '../../../services/auth.service';

const LABELS = ['TRUE', 'FALSE', 'PARTIALLY_TRUE', 'NOT_FOUND_IN_CLAIMED_SOURCE'] as const;
type Label = typeof LABELS[number];

@Component({
  selector: 'app-expert-review-detail',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, RouterLink, VerdictBadgeComponent, ScoreBarComponent],
  templateUrl: './expert-review-detail.html',
  styleUrls: ['./expert-review-detail.scss']
})
export class ExpertReviewDetailComponent implements OnInit {
  private readonly expertSvc = inject(ExpertService);
  private readonly verificationSvc = inject(VerificationService);
  private readonly route = inject(ActivatedRoute);
  private readonly toast = inject(ToastService);
  private readonly fb = inject(FormBuilder);
  private readonly auth = inject(AuthService);

  readonly isAdmin = this.auth.isAdmin;

  readonly loading = signal(true);
  readonly voting = signal(false);
  readonly submitted = signal(false);
  readonly claim = signal<ExpertQueueItem | null>(null);
  readonly aiResult = signal<VerificationResponse | null>(null);
  readonly selectedLabel = signal<Label | null>(null);
  formSubmitted = false;

  // Requirement: at most one top article is ever surfaced on this page, with its full body.
  readonly topArticle = computed<MatchedArticle | null>(() => {
    const articles = this.aiResult()?.matched_articles;
    return articles && articles.length > 0 ? articles[0] : null;
  });

  readonly labels = LABELS;
  readonly labelDisplay: Record<Label, string> = {
    'TRUE': '✓ True',
    'FALSE': '✗ False',
    'PARTIALLY_TRUE': '◑ Partially True',
    'NOT_FOUND_IN_CLAIMED_SOURCE': '? Not Found',
  };

  form = this.fb.group({
    justification: ['', [Validators.required, Validators.minLength(50)]],
  });

  get justInvalid() { return this.form.get('justification')?.invalid && this.form.get('justification')?.touched; }
  get charCount() { return (this.form.value.justification || '').length; }

  selectLabel(lbl: Label): void { this.selectedLabel.set(lbl); }

  ngOnInit(): void {
    const claimId = this.route.snapshot.paramMap.get('id');
    if (!claimId) { this.loading.set(false); return; }

    this.expertSvc.getQueueItem(claimId).subscribe({
      next: c => {
        this.claim.set(c);

        // Also fetch the full AI prediction details (includes full article bodies)
        this.verificationSvc.getResult(claimId).subscribe({
          next: res => { this.aiResult.set(res); this.loading.set(false); },
          error: () => { this.loading.set(false); }
        });
      },
      error: () => this.loading.set(false),
    });
  }

  onSubmit(): void {
    if (this.isAdmin()) { return; } // administrators may view but never vote
    this.formSubmitted = true;
    if (this.form.invalid || !this.selectedLabel()) {
      this.form.markAllAsTouched();
      return;
    }
    const claimId = this.route.snapshot.paramMap.get('id');
    if (!claimId) return;
    this.voting.set(true);

    this.expertSvc.submitVote(claimId, {
      expert_label: this.selectedLabel() as any,
      justification: this.form.value.justification as string,
    }).subscribe({
      next: () => { this.submitted.set(true); this.voting.set(false); this.toast.success('Vote submitted successfully!'); },
      error: err => { this.voting.set(false); this.toast.error(err.error?.message || 'Failed to submit vote.'); },
    });
  }

  getHost(url: string): string {
    try {
      return new URL(url).hostname.replace('www.', '');
    } catch {
      return '';
    }
  }
}
