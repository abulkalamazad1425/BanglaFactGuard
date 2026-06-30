import { Component, Input } from '@angular/core';

@Component({
  selector: 'app-score-bar',
  standalone: true,
  template: `
    <div class="score-bar-wrap">
      <div class="score-bar-header">
        <span class="score-label">{{ label }}</span>
        <span class="score-value" [style.color]="color">{{ (value * 100).toFixed(1) }}%</span>
      </div>
      <div class="score-track">
        <div class="score-fill"
             [style.width.%]="value * 100"
             [style.background]="color">
        </div>
      </div>
    </div>
  `,
  styles: [`
    .score-bar-wrap { width: 100%; }
    .score-bar-header {
      display: flex; justify-content: space-between;
      margin-bottom: 6px; font-size: 13px;
    }
    .score-label { color: var(--text-secondary); }
    .score-value { font-weight: 600; }
    .score-track {
      height: 6px; background: var(--bg-surface-3);
      border-radius: var(--radius-full); overflow: hidden;
    }
    .score-fill {
      height: 100%; border-radius: var(--radius-full);
      transition: width 0.8s cubic-bezier(0.4, 0, 0.2, 1);
    }
  `]
})
export class ScoreBarComponent {
  @Input() label = 'Confidence';
  @Input() value = 0;
  @Input() color = 'var(--primary)';
}
