import { Component, OnInit, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { FormBuilder, FormGroup, FormArray, Validators, ReactiveFormsModule } from '@angular/forms';
import { SourceService } from '../../../services/source.service';
import { SourceResponse } from '../../../models/source.model';
import { ToastService } from '../../../shared/services/toast.service';

@Component({
  selector: 'app-source-management',
  standalone: true,
  imports: [CommonModule, RouterModule, ReactiveFormsModule],
  templateUrl: './source-management.component.html',
  styleUrls: ['./source-management.component.scss']
})
export class SourceManagementComponent implements OnInit {
  protected readonly Math = Math;
  private readonly sourceService = inject(SourceService);
  private readonly toast = inject(ToastService);
  private readonly fb = inject(FormBuilder);

  sources = signal<SourceResponse[]>([]);
  total = signal(0);
  page = signal(1);
  size = 20;

  // Drawer state
  drawerOpen = signal(false);
  isEditMode = signal(false);
  saving = signal(false);
  editingSourceId: string | null = null;

  form: FormGroup = this.fb.group({
    canonical_name: ['', [Validators.required, Validators.pattern(/^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}$/)]],
    display_name: ['', Validators.required],
    display_name_en: [''],
    aliases: this.fb.array([]),
    base_url: ['', [Validators.required, Validators.pattern(/^https?:\/\/.*/)]],
    rss_url: [''],
    language: ['bn', Validators.required],
    search_language: ['bn', Validators.required],
    js_rendered: [false],
    description: [''],
    internal_search_url: [''],
    body_selectors: this.fb.array([]),
    title_selectors: this.fb.array([]),
    date_selectors: this.fb.array([]),
    article_url_patterns: this.fb.array([])
  });

  get aliases() { return this.form.get('aliases') as FormArray; }
  get bodySelectors() { return this.form.get('body_selectors') as FormArray; }
  get titleSelectors() { return this.form.get('title_selectors') as FormArray; }
  get dateSelectors() { return this.form.get('date_selectors') as FormArray; }
  get articleUrlPatterns() { return this.form.get('article_url_patterns') as FormArray; }

  ngOnInit() {
    this.loadSources();
  }

  loadSources() {
    this.sourceService.listSources(undefined, this.page(), this.size).subscribe({
      next: (res) => {
        this.sources.set(res.items);
        this.total.set(res.total);
      },
      error: () => this.toast.error('Failed to load sources')
    });
  }

  openRegisterDrawer() {
    this.isEditMode.set(false);
    this.editingSourceId = null;
    this.form.reset({ language: 'bn', search_language: 'bn', js_rendered: false });
    this.clearAllArrays();
    this.form.get('canonical_name')?.enable();
    this.drawerOpen.set(true);
  }

  openEditDrawer(source: SourceResponse) {
    this.isEditMode.set(true);
    this.editingSourceId = source.id;
    this.form.patchValue(source);
    this.form.get('canonical_name')?.disable();
    this.setFormArray('aliases', source.aliases);
    this.setFormArray('body_selectors', source.body_selectors);
    this.setFormArray('title_selectors', source.title_selectors);
    this.setFormArray('date_selectors', source.date_selectors);
    this.setFormArray('article_url_patterns', source.article_url_patterns);
    this.drawerOpen.set(true);
  }

  closeDrawer() {
    this.drawerOpen.set(false);
  }

  clearAllArrays() {
    this.aliases.clear();
    this.bodySelectors.clear();
    this.titleSelectors.clear();
    this.dateSelectors.clear();
    this.articleUrlPatterns.clear();
  }

  setFormArray(name: string, items: string[]) {
    const arr = this.form.get(name) as FormArray;
    arr.clear();
    items?.forEach(item => arr.push(this.fb.control(item)));
  }

  addArrayItem(name: string) {
    const arr = this.form.get(name) as FormArray;
    arr.push(this.fb.control(''));
  }

  removeArrayItem(name: string, index: number) {
    const arr = this.form.get(name) as FormArray;
    arr.removeAt(index);
  }

  onSubmit() {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      this.toast.error('Please fix the validation errors.');
      return;
    }

    this.saving.set(true);
    const raw = this.form.getRawValue();

    const request = this.isEditMode()
      ? this.sourceService.updateSource(this.editingSourceId!, { ...raw, canonical_name: undefined })
      : this.sourceService.createSource(raw);

    request.subscribe({
      next: () => {
        this.toast.success(`Source ${this.isEditMode() ? 'updated' : 'registered'} successfully!`);
        this.saving.set(false);
        this.drawerOpen.set(false);
        this.loadSources();
      },
      error: (err) => {
        this.toast.error(err.error?.detail?.message || 'An error occurred.');
        this.saving.set(false);
      }
    });
  }

  toggleActive(source: SourceResponse) {
    this.sourceService.updateSource(source.id, { is_active: !source.is_active }).subscribe({
      next: (res) => {
        this.sources.update(items => items.map(i => i.id === res.id ? res : i));
        this.toast.success(`Source ${res.is_active ? 'enabled' : 'disabled'}.`);
      },
      error: () => this.toast.error('Failed to update source.')
    });
  }

  deleteSource(source: SourceResponse) {
    if (confirm(`Delete "${source.display_name}"? This action cannot be undone.`)) {
      this.sourceService.deleteSource(source.id).subscribe({
        next: () => {
          this.loadSources();
          this.toast.success('Source deleted.');
        },
        error: () => this.toast.error('Failed to delete source.')
      });
    }
  }

  nextPage() {
    this.page.update(p => p + 1);
    this.loadSources();
  }

  prevPage() {
    if (this.page() > 1) {
      this.page.update(p => p - 1);
      this.loadSources();
    }
  }
}
