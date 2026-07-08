import { Component, inject } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { CommonModule } from '@angular/common';
import { AdminService } from '../../../services/admin.service';
import { ToastService } from '../../../shared/services/toast.service';
import { CreateExpertRequest } from '../../../models/admin.model';

@Component({
  selector: 'app-create-expert',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, RouterLink],
  templateUrl: './create-expert.html',
  styleUrls: ['./create-expert.scss']
})
export class CreateExpertComponent {
  private readonly fb = inject(FormBuilder);
  private readonly adminSvc = inject(AdminService);
  private readonly router = inject(Router);
  private readonly toast = inject(ToastService);

  loading = false;
  errorMsg = '';

  form = this.fb.group({
    full_name: ['', Validators.required],
    email: ['', [Validators.required, Validators.email]],
    password: ['', [Validators.required, Validators.minLength(8), Validators.pattern(/^(?=.*[A-Z])(?=.*\d).+$/)]],
    expertise_area: ['', Validators.required],
  });

  get nameInvalid() { return this.form.get('full_name')?.invalid && this.form.get('full_name')?.touched; }
  get emailInvalid() { return this.form.get('email')?.invalid && this.form.get('email')?.touched; }
  get pwInvalid() { return this.form.get('password')?.invalid && this.form.get('password')?.touched; }
  get areaInvalid() { return this.form.get('expertise_area')?.invalid && this.form.get('expertise_area')?.touched; }

  onSubmit(): void {
    if (this.form.invalid) { this.form.markAllAsTouched(); return; }
    this.loading = true; this.errorMsg = '';

    this.adminSvc.createExpert(this.form.value as CreateExpertRequest).subscribe({
      next: () => { this.toast.success('Expert account created successfully.'); this.router.navigate(['/admin/experts']); },
      error: err => { this.errorMsg = err.error?.message || 'Failed to create expert.'; this.loading = false; },
    });
  }
}
