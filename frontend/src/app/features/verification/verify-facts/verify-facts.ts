import { Component, inject } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { toSignal } from '@angular/core/rxjs-interop';
import { map } from 'rxjs';
import { VerifyClaimComponent } from '../verify-claim/verify-claim';
import { PhotoCardComponent } from '../../photocard/photocard';
import { MultimodalComponent } from '../../multimodal/multimodal';

import { VERIFY_OPTIONS, VerifyMethod } from './verify-options';

const DESC_KEY = 'bfg.verify.hideDescriptions';

@Component({
  selector: 'app-verify-facts',
  standalone: true,
  imports: [VerifyClaimComponent, PhotoCardComponent, MultimodalComponent],
  templateUrl: './verify-facts.html',
  styleUrls: ['./verify-facts.scss'],
})
export class VerifyFactsComponent {
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);

  readonly options = VERIFY_OPTIONS;
  readonly method = toSignal(
    this.route.queryParamMap.pipe(map((q) => {
      const m = q.get('method');
      return VERIFY_OPTIONS.some((o) => o.key === m) ? (m as VerifyMethod) : null;
    })),
    { initialValue: null },
  );

  hideDescriptions = readHidden();

  select(key: VerifyMethod): void {
    this.router.navigate([], { relativeTo: this.route, queryParams: { method: key }, replaceUrl: true });
  }

  toggleDescriptions(): void {
    this.hideDescriptions = !this.hideDescriptions;
    try { localStorage.setItem(DESC_KEY, this.hideDescriptions ? '1' : '0'); } catch { /* storage unavailable */ }
  }
}

function readHidden(): boolean {
  try { return localStorage.getItem(DESC_KEY) === '1'; } catch { return false; }
}
