import { Component, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { CommonModule } from '@angular/common';
import { ToastService } from '../../shared/services/toast.service';
import { MultimodalService } from '../../services/verification.service';
import { MultimodalPredictionResult } from '../../models/verification.model';


@Component({
  selector: 'app-multimodal',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './multimodal.html',
  styleUrls: ['./multimodal.scss'],
})
export class MultimodalComponent {
  private readonly svc = inject(MultimodalService);
  private readonly toast = inject(ToastService);

  headline = '';
  bodyText = '';
  selectedFile: File | null = null;
  previewUrl: string | null = null;

  loading = false;
  submitted = false;
  errorMsg: string | null = null;
  result: MultimodalPredictionResult | null = null;

  onFileChange(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (file) this._setFile(file);
  }

  onDrop(event: DragEvent): void {
    event.preventDefault();
    const file = event.dataTransfer?.files?.[0];
    if (file && file.type.startsWith('image/')) this._setFile(file);
  }

  private _setFile(file: File): void {
    this.selectedFile = file;
    const reader = new FileReader();
    reader.onload = () => (this.previewUrl = reader.result as string);
    reader.readAsDataURL(file);
  }

  onSubmit(): void {
    this.submitted = true;

    if (!this.headline.trim() || this.bodyText.trim().length < 10 || !this.selectedFile) {
      return;
    }

    this.loading = true;
    this.errorMsg = null;
    this.result = null;

    this.svc.predict(this.headline, this.bodyText, this.selectedFile).subscribe({
      next: (r) => {
        this.result = r;
        this.loading = false;
      },
      error: (err) => {
        this.loading = false;
        this.errorMsg = err.error?.detail || err.error?.message || 'An error occurred processing the request.';
        this.toast.error(this.errorMsg!);
      },
    });
  }

  formatDate(isoString: string): string {
    const d = new Date(isoString);
    return d.toLocaleTimeString() + ' ' + d.toLocaleDateString();
  }
}
