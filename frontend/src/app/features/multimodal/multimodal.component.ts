import { Component, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { CommonModule } from '@angular/common';
import { ApiService } from '../../core/services/api.service';
import { ToastService } from '../../shared/services/toast.service';
import { MultimodalPredictionResult } from '../../core/models/verification.model';
import { API_ENDPOINTS } from '../../core/constants/api-endpoints.constant';
import { VerdictBadgeComponent } from '../../shared/components/verdict-badge/verdict-badge.component';
import { ScoreBarComponent } from '../../shared/components/score-bar/score-bar.component';

@Component({
  selector: 'app-multimodal',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, VerdictBadgeComponent, ScoreBarComponent],
  template: `
    <div class="mm-page">
      <div class="container container-sm" style="padding-top:48px;padding-bottom:80px;">
        <div class="page-header text-center animate-in">
          <div class="page-icon">🖼️</div>
          <h1>Multimodal Fake News Detection</h1>
          <p>Upload a news image and provide the associated text. Our BanglaBERT + EfficientNet-B4 model will analyze both.</p>
        </div>

        <div class="card animate-in" style="animation-delay:0.1s; padding:40px;">
          <form [formGroup]="form" (ngSubmit)="onSubmit()">
            <!-- Image Upload -->
            <div class="form-group">
              <label class="form-label">News Image <span style="color:var(--error)">*</span></label>
              <div class="upload-zone" [class.has-image]="previewUrl()" (click)="fileInput.click()" (dragover)="$event.preventDefault()" (drop)="onDrop($event)">
                @if (previewUrl()) {
                  <img [src]="previewUrl()!" alt="Preview" class="upload-preview" />
                  <div class="upload-overlay">
                    <span>Click to change image</span>
                  </div>
                } @else {
                  <div class="upload-placeholder">
                    <div class="upload-icon">📁</div>
                    <p><strong>Click or drag & drop</strong> an image here</p>
                    <span class="text-muted text-sm">PNG, JPG, WEBP — max 10MB</span>
                  </div>
                }
              </div>
              <input #fileInput type="file" accept="image/*" class="sr-only" (change)="onFileChange($event)" />
              @if (!selectedFile() && submitted) {
                <span class="form-error">Image is required</span>
              }
            </div>

            <!-- Text Input -->
            <div class="form-group">
              <label class="form-label">Associated News Text <span style="color:var(--error)">*</span></label>
              <textarea formControlName="text" class="form-control"
                        [class.is-invalid]="textInvalid" rows="5"
                        placeholder="Paste the Bangla news text associated with this image..."></textarea>
              @if (textInvalid) {
                <span class="form-error">News text is required (min 20 characters)</span>
              }
            </div>

            <button type="submit" class="btn btn-primary btn-full btn-lg" [disabled]="loading()">
              @if (loading()) {
                <span class="btn-spinner"></span> Analyzing...
              } @else {
                🔍 Analyze for Fake News
              }
            </button>
          </form>
        </div>

        <!-- Result -->
        @if (result()) {
          <div class="card result-card animate-in" style="margin-top:24px;">
            <h3 class="section-title">Analysis Result</h3>
            <div class="result-verdict">
              <app-verdict-badge [label]="mapLabel(result()!.label)" />
              <span class="result-label">{{ result()!.label === 'FAKE' ? 'Likely Fake News' : 'Likely Real News' }}</span>
            </div>
            <div style="max-width:380px; margin-top:20px;">
              <app-score-bar label="Confidence" [value]="result()!.confidence"
                             [color]="result()!.label === 'FAKE' ? 'var(--error)' : 'var(--success)'" />
            </div>
            @if (result()!.processing_time_ms) {
              <p class="text-muted text-sm mt-4">⚡ Processed in {{ (result()!.processing_time_ms! / 1000).toFixed(1) }}s</p>
            }
          </div>
        }
      </div>
    </div>
  `,
  styles: [`
    .mm-page { background: var(--bg-base); min-height: 100%; }
    .page-header { margin-bottom: 48px; }
    .page-icon { font-size: 64px; margin-bottom: 20px; }
    .page-header h1 { margin-bottom: 12px; }
    .page-header p { color: var(--text-secondary); font-size: 16px; max-width: 520px; margin: 0 auto; }
    .form-group { margin-bottom: 24px; }
    .upload-zone {
      position: relative; border: 2px dashed var(--border); border-radius: var(--radius-lg);
      min-height: 200px; cursor: pointer; display: flex; align-items: center; justify-content: center;
      transition: var(--transition); overflow: hidden;
      &:hover { border-color: var(--primary); }
      &.has-image { border-style: solid; }
    }
    .upload-placeholder { text-align: center; padding: 40px; }
    .upload-icon { font-size: 48px; margin-bottom: 16px; }
    .upload-preview { width: 100%; max-height: 300px; object-fit: cover; }
    .upload-overlay {
      position: absolute; inset: 0; background: rgba(0,0,0,0.6);
      display: flex; align-items: center; justify-content: center;
      color: white; font-weight: 600; opacity: 0; transition: var(--transition);
    }
    .upload-zone:hover .upload-overlay { opacity: 1; }
    .result-card { }
    .result-verdict { display: flex; align-items: center; gap: 16px; flex-wrap: wrap; margin-bottom: 8px; }
    .result-label { font-size: 1.25rem; font-weight: 700; }
    .section-title { font-size: 16px; margin-bottom: 20px; }
    .btn-spinner { width: 18px; height: 18px; border: 2px solid rgba(255,255,255,0.3); border-top-color: white; border-radius: 50%; animation: spin 0.7s linear infinite; }
  `]
})
export class MultimodalComponent {
  private readonly api = inject(ApiService);
  private readonly toast = inject(ToastService);
  private readonly fb = inject(FormBuilder);

  readonly loading = signal(false);
  readonly selectedFile = signal<File | null>(null);
  readonly previewUrl = signal<string | null>(null);
  readonly result = signal<MultimodalPredictionResult | null>(null);
  submitted = false;

  form = this.fb.group({
    text: ['', [Validators.required, Validators.minLength(20)]],
  });

  get textInvalid() { return this.form.get('text')?.invalid && this.form.get('text')?.touched; }

  mapLabel(label: string): string {
    return label === 'FAKE' ? 'FALSE' : 'TRUE';
  }

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
    this.selectedFile.set(file);
    const reader = new FileReader();
    reader.onload = () => this.previewUrl.set(reader.result as string);
    reader.readAsDataURL(file);
  }

  onSubmit(): void {
    this.submitted = true;
    if (this.form.invalid || !this.selectedFile()) {
      this.form.markAllAsTouched();
      return;
    }
    this.loading.set(true);
    this.result.set(null);

    const fd = new FormData();
    fd.append('image', this.selectedFile()!);
    fd.append('text', this.form.value.text!);

    this.api.postFormData<MultimodalPredictionResult>(API_ENDPOINTS.MULTIMODAL_PREDICT, fd).subscribe({
      next: r => { this.result.set(r); this.loading.set(false); },
      error: err => {
        this.loading.set(false);
        this.toast.error(err.error?.message || 'Multimodal analysis failed.');
      },
    });
  }
}
