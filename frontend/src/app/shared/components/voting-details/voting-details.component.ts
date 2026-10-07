import { DatePipe } from '@angular/common';
import { Component, Input, inject, signal } from '@angular/core';
import { PublicVotingDetails } from '../../../models/verification.model';
import { SubmissionsService } from '../../../services/submissions.service';
import { VerdictBadgeComponent } from '../verdict-badge/verdict-badge.component';

/**
 * Public "Voting Details" for a claim with a final decision: each reviewer's
 * overall vote and justification, with an admin's final decision marked.
 * Rendered only after finalization (the API also refuses before that), and
 * loaded on first open so the result page stays light.
 */
@Component({
  selector: 'app-voting-details',
  standalone: true,
  imports: [DatePipe, VerdictBadgeComponent],
  template: `
    <div class="voting-details">
      <button
        type="button"
        class="btn btn-secondary toggle"
        [attr.aria-expanded]="open()"
        aria-controls="voting-details-panel"
        (click)="toggle()"
      >
        <span aria-hidden="true">{{ open() ? '▾' : '▸' }}</span> Voting Details
      </button>
      @if (open()) {
        <div id="voting-details-panel" class="panel" role="region" aria-label="Voting details">
          @if (loading()) {
            <p class="state" role="status">Loading reviewer votes…</p>
          } @else if (error()) {
            <p class="state" role="alert"
              >Voting details could not be loaded.
              <button type="button" class="link-button" (click)="load()">Try again</button></p
            >
          }
          @if (!loading() && !error() && details(); as d) {
            <ol class="votes">
              @for (v of d.votes; track $index) {
                <li class="vote" [class.final]="v.is_final_decision">
                  <div class="vote-head">
                    <div
                      ><strong>{{ v.reviewer_name }}</strong>
                      <span class="role">{{ v.reviewer_role }}</span>
                      @if (v.is_final_decision) {
                        <span class="final-tag">Final decision</span>
                      }
                    </div>
                    <span class="vote-value"
                      >Vote: <app-verdict-badge [overallVerdict]="v.overall_vote"
                    /></span>
                  </div>
                  <p class="justification">{{
                    v.justification || 'No justification was recorded.'
                  }}</p>
                  <small>Voted {{ v.voted_at | date: 'd MMM y, h:mm a' }}</small>
                </li>
              }
            </ol>
          }
        </div>
      }
    </div>
  `,
  styles: [
    `
      :host {
        display: block;
      }
      .toggle {
        margin-top: 16px;
      }
      .panel {
        margin-top: 14px;
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 16px;
        background: var(--bg-surface);
      }
      .summary {
        font-size: 14px;
        margin: 0 0 12px;
      }
      .votes {
        list-style: none;
        padding: 0;
        margin: 0;
        display: grid;
        gap: 12px;
      }
      .vote {
        border: 1px solid var(--border);
        border-left: 4px solid var(--border-strong, #94a3a0);
        border-radius: 10px;
        padding: 14px 16px;
      }
      .vote.final {
        border-left-color: var(--primary);
        background: var(--bg-surface-2);
      }
      .vote-head {
        display: flex;
        flex-wrap: wrap;
        justify-content: space-between;
        align-items: center;
        gap: 8px 16px;
      }
      .role {
        font-size: 12px;
        color: var(--text-muted);
        margin-left: 4px;
      }
      .final-tag {
        display: inline-block;
        margin-left: 8px;
        font-size: 11px;
        font-weight: 800;
        letter-spacing: 0.04em;
        text-transform: uppercase;
        padding: 2px 8px;
        border-radius: 4px;
        background: var(--primary);
        color: #fff;
      }
      .vote-value {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        font-size: 13px;
        color: var(--text-secondary);
      }
      .justification {
        margin: 10px 0 6px;
        font-size: 14px;
        line-height: 1.8;
        white-space: pre-wrap;
        overflow-wrap: anywhere;
        color: var(--text-primary);
      }
      small {
        color: var(--text-muted);
        font-size: 12px;
      }
      .state {
        margin: 0;
        font-size: 14px;
      }
      .link-button {
        background: none;
        border: 0;
        padding: 0;
        min-height: 0;
        color: var(--primary);
        text-decoration: underline;
        cursor: pointer;
        font: inherit;
      }
    `,
  ],
})
export class VotingDetailsComponent {
  private readonly submissions = inject(SubmissionsService);
  @Input({ required: true }) submissionId!: string;

  readonly open = signal(false);
  readonly loading = signal(false);
  readonly error = signal(false);
  readonly details = signal<PublicVotingDetails | null>(null);

  toggle(): void {
    this.open.update((v) => !v);
    if (this.open() && !this.details() && !this.loading()) this.load();
  }

  load(): void {
    this.loading.set(true);
    this.error.set(false);
    this.submissions.getVotingDetails(this.submissionId).subscribe({
      next: (d) => {
        this.details.set(d);
        this.loading.set(false);
      },
      error: () => {
        this.error.set(true);
        this.loading.set(false);
      },
    });
  }
}
