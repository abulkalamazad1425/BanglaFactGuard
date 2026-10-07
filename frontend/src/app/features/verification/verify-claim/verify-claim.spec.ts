import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { of, throwError } from 'rxjs';
import { VerifyClaimComponent } from './verify-claim';
import { VerificationService } from '../../../services/verification.service';
import { SourceService } from '../../../services/source.service';
import { PendingVerificationsService } from '../../../services/pending-verifications.service';
import { ToastService } from '../../../shared/services/toast.service';

describe('News submission recovery', () => {
  it('keeps the received claim link when a saved result cannot load', () => {
    const service = jasmine.createSpyObj('VerificationService', ['submitAsync', 'getResult']);
    service.submitAsync.and.returnValue(
      of({ submission_id: 's1', cached: true, status: 'EXPERT_REVIEW' }),
    );
    service.getResult.and.returnValue(throwError(() => ({ status: 503 })));
    TestBed.configureTestingModule({
      imports: [VerifyClaimComponent],
      providers: [
        provideRouter([]),
        { provide: VerificationService, useValue: service },
        { provide: SourceService, useValue: { listSources: () => of({ items: [] }) } },
        { provide: PendingVerificationsService, useValue: {} },
        { provide: ToastService, useValue: { error: () => {} } },
      ],
    });
    const fixture = TestBed.createComponent(VerifyClaimComponent);
    const c = fixture.componentInstance;
    c.form.patchValue({ headline: 'খবরের সম্পূর্ণ শিরোনাম', claimed_source_text: 'news.example' });
    c.onSubmit();
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Result temporarily unavailable');
    expect(fixture.nativeElement.querySelector('a[href="/verify/s1"]')).not.toBeNull();
    expect(c.form.value.headline).toBe('খবরের সম্পূর্ণ শিরোনাম');
  });
});
