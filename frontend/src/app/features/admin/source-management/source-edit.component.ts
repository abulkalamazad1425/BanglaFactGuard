import { Component, OnInit, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, FormGroup, FormArray, Validators, ReactiveFormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterModule } from '@angular/router';
import { SourceService } from '../../../services/source.service';
import { ToastService } from '../../../shared/services/toast.service';

@Component({
  selector: 'app-source-edit',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, RouterModule],
  templateUrl: './source-edit.component.html',
  styleUrls: ['./source-edit.component.scss']
})
export class SourceEditComponent implements OnInit {
  private readonly fb = inject(FormBuilder);
  private readonly sourceService = inject(SourceService);
  private readonly toast = inject(ToastService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);

  isEditMode = signal(false);
  sourceId: string | null = null;
  
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

  ngOnInit() {
    this.sourceId = this.route.snapshot.paramMap.get('id');
    if (this.sourceId && this.sourceId !== 'new') {
      this.isEditMode.set(true);
      this.loadSource();
    }
  }

  loadSource() {
    if (!this.sourceId) return;
    this.sourceService.getSource(this.sourceId).subscribe({
      next: (source) => {
        this.form.patchValue(source);
        this.setFormArray('aliases', source.aliases);
        this.setFormArray('body_selectors', source.body_selectors);
        this.setFormArray('title_selectors', source.title_selectors);
        this.setFormArray('date_selectors', source.date_selectors);
        this.setFormArray('article_url_patterns', source.article_url_patterns);
      },
      error: () => {
        this.toast.error('Failed to load source details');
        this.router.navigate(['/admin/sources']);
      }
    });
  }

  get aliases() { return this.form.get('aliases') as FormArray; }
  get bodySelectors() { return this.form.get('body_selectors') as FormArray; }
  get titleSelectors() { return this.form.get('title_selectors') as FormArray; }
  get dateSelectors() { return this.form.get('date_selectors') as FormArray; }
  get articleUrlPatterns() { return this.form.get('article_url_patterns') as FormArray; }

  setFormArray(name: string, items: string[]) {
    const arr = this.form.get(name) as FormArray;
    arr.clear();
    items?.forEach(item => arr.push(this.fb.control(item)));
  }

  addArrayItem(name: string) {
    const arr = this.form.get(name) as FormArray;
    arr.push(this.fb.control('', Validators.required));
  }

  removeArrayItem(name: string, index: number) {
    const arr = this.form.get(name) as FormArray;
    arr.removeAt(index);
  }

  onSubmit() {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      this.toast.error('Please fix the errors in the form.');
      return;
    }
    
    const data = this.form.value;
    
    // In edit mode, canonical_name should be removed as it cannot be modified
    const request = this.isEditMode() 
      ? this.sourceService.updateSource(this.sourceId!, {
          ...data,
          canonical_name: undefined // don't send canonical_name on update
        })
      : this.sourceService.createSource(data);
      
    request.subscribe({
      next: () => {
        this.toast.success(`Source successfully ${this.isEditMode() ? 'updated' : 'created'}`);
        this.router.navigate(['/admin/sources']);
      },
      error: (err) => {
        this.toast.error(err.error?.detail?.message || 'An error occurred');
      }
    });
  }
}
