import { requestError } from '../../shared/utils/presentation';
import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { ToastService } from '../../shared/services/toast.service';
import { AuthService } from '../../services/auth.service';
import { verificationFollowUp } from '../../shared/utils/status-labels';
import { PhotoCardService } from '../../services/photocard.service';
import { PendingVerificationsService } from '../../services/pending-verifications.service';
import { SourceService } from '../../services/source.service';
import { SourceResponse } from '../../models/source.model';
import { PhotoCardAccepted } from '../../models/photocard.model';

type Step = 'upload' | 'accepted';

/**
 * Photo-card verification — the image is the whole submission.
 *
 * The user only uploads the card. The server stores it, queues a durable job
 * and answers 202 immediately. There, Gemini reads the headline, identifies
 * the news outlet among the currently active verified sources (by its name,
 * logo or a known alias) and reads the printed date; those become the claim's
 * headline, claimed outlet and claimed date, and the headline is verified.
 * Leaving this page does not cancel anything — the result is fetched later by
 * submission id (My Submissions, the notification link, or the result page).
 *
 * The outlets a card may come from are listed beside the form (collapsed by
 * default, like the article text on a result page).
 */
@Component({
  selector: 'app-photocard',
  standalone: true,
  imports: [CommonModule, RouterLink],
  templateUrl: './photocard.html',
  styleUrls: ['./photocard.scss'],
})
export class PhotoCardComponent implements OnInit {
  private readonly svc = inject(PhotoCardService);
  private readonly sourceSvc = inject(SourceService);
  private readonly toast = inject(ToastService);
  private readonly pending = inject(PendingVerificationsService);
  /** Signed-in and anonymous users are told different next steps. */
  readonly signedIn = inject(AuthService).isLoggedIn;
  readonly followUp = verificationFollowUp;

  step: Step = 'upload';

  // ── Upload form ──
  selectedFile: File | null = null;
  previewUrl: string | null = null;
  dragActive = false;
  submitted = false;
  /** True only while the (fast) upload itself is in flight. */
  verifying = false;

  // ── Accepted ──
  accepted: PhotoCardAccepted | null = null;

  errorMsg: string | null = null;

  /** Active verified sources — the only outlets a card can be checked against. */
  sources: SourceResponse[] = [];
  sourcesLoading = true;
  sourcesError = false;

  ngOnInit(): void {
    this.loadSources();
  }

  loadSources(): void {
    this.sourcesLoading = true;
    this.sourcesError = false;
    this.sourceSvc.listSources(undefined, 1, 100).subscribe({
      next: (res) => {
        this.sources = res.items
          .filter((s) => s.is_active !== false)
          .sort((a, b) => a.display_name.localeCompare(b.display_name, 'bn'));
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
    if (
      !'image/jpeg,image/png,image/webp,image/gif'.split(',').includes(file.type) ||
      file.size > 10 * 1024 * 1024 ||
      file.size === 0
    ) {
      this.errorMsg = 'Choose a supported, non-empty image under 10 MB.';
      this.selectedFile = null;
      this.previewUrl = null;
      return;
    }
    this.errorMsg = null;
    this.selectedFile = file;
    const reader = new FileReader();
    reader.onload = () => (this.previewUrl = reader.result as string);
    reader.readAsDataURL(file);
  }

  get canVerify(): boolean {
    return !!this.selectedFile;
  }

  verify(): void {
    this.submitted = true;
    if (!this.canVerify || !this.selectedFile) return;

    this.verifying = true;
    this.errorMsg = null;

    this.svc.submitAsync({ image: this.selectedFile }).subscribe({
      next: (res) => {
        this.verifying = false;
        this.accepted = res;
        this.step = 'accepted';
        // Lets the app tell the user when the result lands while they are
        // elsewhere in the app; the server job does not depend on this. The
        // outlet is not known until the card has been read.
        this.pending.track(res.submission_id, 'Photo card', '', 'PHOTO_CARD');
      },
      error: (err) => {
        this.verifying = false;
        this.errorMsg = requestError(
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
    this.submitted = false;
    this.errorMsg = null;
  }
}
