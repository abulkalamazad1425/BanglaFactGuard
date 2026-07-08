import { Component, OnInit, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { VerificationService } from '../../../services/verification.service';
import { SubmissionSummary, SubmissionStats } from '../../../models/verification.model';
import { VerdictBadgeComponent } from '../../../shared/components/verdict-badge/verdict-badge.component';

@Component({
  selector: 'app-submission-history',
  standalone: true,
  imports: [CommonModule, RouterLink, VerdictBadgeComponent],
  templateUrl: './submission-history.html',
  styleUrls: ['./submission-history.scss']
})
export class SubmissionHistoryComponent implements OnInit {
  private readonly verificationSvc = inject(VerificationService);

  readonly loading = signal(true);
  readonly submissions = signal<SubmissionSummary[]>([]);
  readonly stats = signal<SubmissionStats | null>(null);
  readonly offset = signal(0);
  readonly limit = 20;

  readonly page = () => Math.floor(this.offset() / this.limit) + 1;

  ngOnInit(): void {
    this.verificationSvc.getMyStats().subscribe({
      next: s => this.stats.set(s), error: () => { }
    });
    this.load();
  }

  load(): void {
    this.loading.set(true);
    this.verificationSvc.getMySubmissions(this.limit, this.offset())
      .subscribe({ next: s => { this.submissions.set(s); this.loading.set(false); }, error: () => this.loading.set(false) });
  }

  prev(): void { this.offset.update(o => Math.max(0, o - this.limit)); this.load(); }
  next(): void { this.offset.update(o => o + this.limit); this.load(); }
}
