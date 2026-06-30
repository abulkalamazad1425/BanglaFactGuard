import { Component, Input } from '@angular/core';
import { NgClass } from '@angular/common';
import { VerificationLabel } from '../../../core/models/verification.model';

const LABEL_CONFIG: Record<string, { text: string; cls: string; icon: string }> = {
  'TRUE':                         { text: 'True',            cls: 'badge-true',      icon: '✓' },
  'FALSE':                        { text: 'False',           cls: 'badge-false',     icon: '✗' },
  'PARTIALLY_TRUE':               { text: 'Partially True',  cls: 'badge-partial',   icon: '◑' },
  'NOT_FOUND_IN_CLAIMED_SOURCE':  { text: 'Not Found',       cls: 'badge-not-found', icon: '?' },
};

@Component({
  selector: 'app-verdict-badge',
  standalone: true,
  imports: [NgClass],
  template: `
    @if (config) {
      <span class="badge" [ngClass]="config.cls">
        <span class="badge-icon">{{ config.icon }}</span>
        {{ config.text }}
      </span>
    }
  `,
  host: { '[class.inline]': 'true' },
  styles: [`
    :host { display: inline-flex; }
    .badge-icon { font-weight: 700; }
  `],
})
export class VerdictBadgeComponent {
  @Input() set label(val: string | null | undefined) {
    this.config = val ? LABEL_CONFIG[val] ?? null : null;
  }

  config: { text: string; cls: string; icon: string } | null = null;
}
