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
  readonly signedIn = inject(AuthService).isLoggedIn;
  readonly followUp = verificationFollowUp;

  step: Step = 'upload';

  selectedFile: File | null = null;
  previewUrl: string | null = null;
  dragActive = false;
  submitted = false;
  verifying = false;

  accepted: PhotoCardAccepted | null = null;

  errorMsg: string | null = null;

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
