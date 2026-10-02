import { requestError } from '../../shared/utils/presentation';
import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { ToastService } from '../../shared/services/toast.service';
import { PhotoCardService } from '../../services/photocard.service';
import { PendingVerificationsService } from '../../services/pending-verifications.service';
import { SourceService } from '../../services/source.service';
import { SourceResponse } from '../../models/source.model';
import { PhotoCardAccepted } from '../../models/photocard.model';

type Step = 'upload' | 'accepted';

/**
 * Photo-card verification — accepted fast, processed in the background.
 *
 * Upload the card with the claimed source and (optionally) its published
 * date. The server stores the image, queues a durable job and answers 202
 * immediately. OCR, headline extraction (Gemini first, deterministic fallback)
 * and the shared verification pipeline then run on the SERVER — leaving this
 * page, closing the tab or navigating elsewhere does not cancel anything. The
 * result is fetched later by submission id (My Submissions, the notification
 * link, or the result page), and is identical to what a viewer who stayed
 * would see.
 *
 * The card is always verified against its headline alone, and the claimed
 * source/date entered here are the verification targets — never silently
 * replaced by what the card's own text implies.
 */
@Component({
  selector: 'app-photocard',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  templateUrl: './photocard.html',
  styleUrls: ['./photocard.scss'],
})
export class PhotoCardComponent implements OnInit {
  private readonly svc = inject(PhotoCardService);
  private readonly sourceSvc = inject(SourceService);
  private readonly toast = inject(ToastService);
  private readonly pending = inject(PendingVerificationsService);

  step: Step = 'upload';

  // ── Upload form ──
  selectedFile: File | null = null;
  previewUrl: string | null = null;
  dragActive = false;
  claimedSource = '';
  publishedDate = '';
  forceRefresh = false;
  submitted = false;
  /** True only while the (fast) upload itself is in flight. */
  verifying = false;

  // ── Accepted ──
  accepted: PhotoCardAccepted | null = null;

  errorMsg: string | null = null;

  sources: SourceResponse[] = [];
  sourcesLoading = true;
  sourcesError = false;

  ngOnInit(): void { this.loadSources(); }

  loadSources(): void {
    this.sourcesLoading = true;
    this.sourcesError = false;
    // Only active verified sources may be verified against.
    this.sourceSvc.listSources(undefined, 1, 100).subscribe({
      next: (res) => {
        this.sources = [...res.items].sort((a, b) =>
          a.display_name.localeCompare(b.display_name, 'bn'),
        );
        this.sourcesLoading = false;
      },
      error: () => {
        this.sourcesError = true;
        this.sourcesLoading = false;
      },
    });
  }

  /* ─── Upload ─── */

  onFileChange(event: Event): void {
    const file = (event.target as HTMLInputElement).files?.[0];
    if (file) this.setFile(file);
  }

  onDrop(event: DragEvent): void {
    event.preventDefault();
    this.dragActive = false;
    const file = event.dataTransfer?.files?.[0];
    if (file) this.setFile(file);
  }

  onDragOver(event: DragEvent): void {
    event.preventDefault();
    this.dragActive = true;
  }

  onDragLeave(): void {
    this.dragActive = false;
  }

  private setFile(file: File): void {
    if (this.verifying) return;
    if (!'image/jpeg,image/png,image/webp,image/gif'.split(',').includes(file.type) || file.size > 10 * 1024 * 1024 || file.size === 0) {
      this.errorMsg = 'Choose a supported, non-empty image under 10 MB.';
      this.selectedFile = null; this.previewUrl = null;
      return;
    }
    this.errorMsg = null;
    this.selectedFile = file;
    this.errorMsg = null;
    const reader = new FileReader();
    reader.onload = () => (this.previewUrl = reader.result as string);
    reader.readAsDataURL(file);
  }

  get canVerify(): boolean {
    return !!this.selectedFile && !!this.claimedSource;
  }

  verify(): void {
    this.submitted = true;
    if (!this.canVerify || !this.selectedFile) return;

    this.verifying = true;
    this.errorMsg = null;

    this.svc
      .submitAsync({
        image: this.selectedFile,
        claimed_source_text: this.claimedSource,
        published_date: this.publishedDate || null,
        force_refresh: this.forceRefresh,
      })
      .subscribe({
        next: (res) => {
          this.verifying = false;
          this.accepted = res;
          this.step = 'accepted';
          // Lets the app tell the user when the result lands while they are
          // elsewhere in the app; the server job does not depend on this.
          this.pending.track(res.submission_id, 'Photo card', this.claimedSourceName(), 'PHOTO_CARD');
        },
        error: (err) => {
          this.verifying = false;
          this.errorMsg = this.readError(
            err,
            'The card could not be submitted. Check your connection and try again.',
          );
          this.toast.error(this.errorMsg);
        },
      });
  }

  reset(): void {
    this.step = 'upload';
    this.selectedFile = null;
    this.previewUrl = null;
    this.accepted = null;
    this.claimedSource = '';
    this.publishedDate = '';
    this.forceRefresh = false;
    this.submitted = false;
    this.errorMsg = null;
  }

  /* ─── Template helpers ─── */

  claimedSourceName(): string {
    const src = this.sources.find((x) => x.canonical_name === this.claimedSource);
    return src?.display_name ?? this.claimedSource;
  }

  private readError(err: any, fallback: string): string {
    return requestError(err, fallback);
  }
}
