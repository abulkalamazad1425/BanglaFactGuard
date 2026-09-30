import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ToastService } from '../../shared/services/toast.service';
import { PhotoCardService } from '../../services/photocard.service';
import { SourceService } from '../../services/source.service';
import { SourceResponse } from '../../models/source.model';
import {
  NOISE_REASON_LABELS,
  OcrLine,
  PhotoCardExtractResponse,
  PhotoCardVerifyResponse,
} from '../../models/photocard.model';

type Step = 'upload' | 'review' | 'result';

/**
 * Photo-card verification — a three-step wizard.
 *
 * The middle step is the point of the whole feature: OCR is never perfect on
 * Bangla, so the user confirms (and corrects) the extracted claim before
 * anything is verified. Only text they have signed off on reaches the
 * pipeline.
 */
@Component({
  selector: 'app-photocard',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './photocard.html',
  styleUrls: ['./photocard.scss'],
})
export class PhotoCardComponent implements OnInit {
  private readonly svc = inject(PhotoCardService);
  private readonly sourceSvc = inject(SourceService);
  private readonly toast = inject(ToastService);

  step: Step = 'upload';

  // ── Step 1: upload ──
  selectedFile: File | null = null;
  previewUrl: string | null = null;
  dragActive = false;
  extracting = false;

  // ── Step 2: review & confirm ──
  draft: PhotoCardExtractResponse | null = null;
  headline = '';
  bodyText = '';
  claimedSource = '';
  publishedDate = '';
  forceRefresh = false;
  showRemovedLines = false;
  showRawText = false;
  verifying = false;
  submitted = false;

  // ── Step 3: result ──
  result: PhotoCardVerifyResponse | null = null;

  errorMsg: string | null = null;

  sources: SourceResponse[] = [];
  sourcesLoading = true;

  ngOnInit(): void {
    // Only active verified sources may be verified against.
    this.sourceSvc.listSources(undefined, 1, 100).subscribe({
      next: (res) => {
        this.sources = [...res.items].sort((a, b) =>
          a.display_name.localeCompare(b.display_name, 'bn'),
        );
        this.sourcesLoading = false;
      },
      error: () => {
        this.sourcesLoading = false;
      },
    });
  }

  /* ─── Step 1: upload ─── */

  onFileChange(event: Event): void {
    const file = (event.target as HTMLInputElement).files?.[0];
    if (file) this.setFile(file);
  }

  onDrop(event: DragEvent): void {
    event.preventDefault();
    this.dragActive = false;
    const file = event.dataTransfer?.files?.[0];
    if (file && file.type.startsWith('image/')) this.setFile(file);
  }

  onDragOver(event: DragEvent): void {
    event.preventDefault();
    this.dragActive = true;
  }

  onDragLeave(): void {
    this.dragActive = false;
  }

  private setFile(file: File): void {
    this.selectedFile = file;
    this.errorMsg = null;
    const reader = new FileReader();
    reader.onload = () => (this.previewUrl = reader.result as string);
    reader.readAsDataURL(file);
  }

  extract(): void {
    if (!this.selectedFile) return;

    this.extracting = true;
    this.errorMsg = null;

    this.svc.extract(this.selectedFile).subscribe({
      next: (draft) => {
        this.extracting = false;
        this.draft = draft;
        this.headline = draft.suggested_headline;
        this.bodyText = draft.suggested_body ?? '';
        // Pre-select the outlet only when detection was confident enough for
        // the backend to promote it; otherwise the user picks it themselves.
        this.claimedSource = draft.primary_source?.canonical_name ?? '';
        this.step = 'review';
      },
      error: (err) => {
        this.extracting = false;
        this.errorMsg = this.readError(
          err,
          'Could not read the photo card. Try a sharper or larger image.',
        );
        this.toast.error(this.errorMsg);
      },
    });
  }

  /* ─── Step 2: review & confirm ─── */

  get canVerify(): boolean {
    return this.headline.trim().length >= 5 && !!this.claimedSource;
  }

  verify(): void {
    this.submitted = true;
    if (!this.draft || !this.canVerify) return;

    this.verifying = true;
    this.errorMsg = null;

    this.svc
      .verify({
        draft_id: this.draft.draft_id,
        headline: this.headline.trim(),
        body_text: this.bodyText.trim() || null,
        claimed_source_text: this.claimedSource,
        published_date: this.publishedDate || null,
        force_refresh: this.forceRefresh,
      })
      .subscribe({
        next: (res) => {
          this.verifying = false;
          this.result = res;
          this.step = 'result';
        },
        error: (err) => {
          this.verifying = false;
          this.errorMsg = this.readError(
            err,
            'Verification failed. Ensure the API server is running on port 8000.',
          );
          this.toast.error(this.errorMsg);
        },
      });
  }

  backToUpload(): void {
    this.step = 'upload';
    this.errorMsg = null;
    this.submitted = false;
  }

  restoreSuggested(): void {
    if (!this.draft) return;
    this.headline = this.draft.suggested_headline;
    this.bodyText = this.draft.suggested_body ?? '';
  }

  reset(): void {
    this.step = 'upload';
    this.selectedFile = null;
    this.previewUrl = null;
    this.draft = null;
    this.result = null;
    this.headline = '';
    this.bodyText = '';
    this.claimedSource = '';
    this.publishedDate = '';
    this.forceRefresh = false;
    this.submitted = false;
    this.errorMsg = null;
    this.showRemovedLines = false;
    this.showRawText = false;
  }

  /* ─── Template helpers ─── */

  get keptLines(): OcrLine[] {
    return this.draft?.lines.filter((line) => !line.is_noise) ?? [];
  }

  get removedLines(): OcrLine[] {
    return this.draft?.lines.filter((line) => line.is_noise) ?? [];
  }

  noiseLabel(reason?: string | null): string {
    return reason ? (NOISE_REASON_LABELS[reason] ?? reason) : 'Excluded';
  }

  percent(value?: number | null): string {
    return value == null ? '—' : `${(value * 100).toFixed(0)}%`;
  }

  verdictColor(label: string): string {
    const map: Record<string, string> = {
      TRUE: '#16a34a',
      FALSE: '#dc2626',
      PARTIALLY_TRUE: '#c2760a',
      NOT_FOUND_IN_CLAIMED_SOURCE: '#6b7280',
    };
    return map[label] ?? '#6b7280';
  }

  getBadgeClass(label: string): string {
    switch (label?.toUpperCase()) {
      case 'TRUE':
        return 'true';
      case 'FALSE':
        return 'false';
      case 'PARTIALLY_TRUE':
        return 'partial';
      default:
        return 'notfound';
    }
  }

  getBadgeIcon(label: string): string {
    switch (label?.toUpperCase()) {
      case 'TRUE':
        return '✓';
      case 'FALSE':
        return '✗';
      case 'PARTIALLY_TRUE':
        return '⚠';
      default:
        return '?';
    }
  }

  formatVerdict(label: string): string {
    return label ? label.replace(/_/g, ' ') : '';
  }

  /** Circumference of the r=45 confidence ring is ~283. */
  getDashOffset(confidence: number): number {
    return 283 - 283 * (confidence || 0);
  }

  getHost(url: string): string {
    try {
      return new URL(url).hostname.replace('www.', '');
    } catch {
      return '';
    }
  }

  private readError(err: any, fallback: string): string {
    const detail = err?.error?.detail;
    if (typeof detail === 'string') return detail;
    return detail?.message || err?.error?.message || fallback;
  }
}
