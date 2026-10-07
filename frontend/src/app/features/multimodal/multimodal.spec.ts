import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { Subject, of } from 'rxjs';
import { MultimodalComponent } from './multimodal';
import { MultimodalService } from '../../services/verification.service';
import { ToastService } from '../../shared/services/toast.service';
import { MultimodalPredictionResult } from '../../models/verification.model';

const RESULT = {
  submission_id: 'm1',
  prediction: 'FAKE',
  expert_overall_verdict: 'REAL',
  created_at: '2026-10-02T00:00:00Z',
  is_cached: false,
} as MultimodalPredictionResult;
describe('Text and image redesigned flow', () => {
  let service: jasmine.SpyObj<MultimodalService>;
  beforeEach(() => {
    service = jasmine.createSpyObj('MultimodalService', ['submitAsync']);
    TestBed.configureTestingModule({
      imports: [MultimodalComponent],
      providers: [
        provideRouter([]),
        { provide: MultimodalService, useValue: service },
        { provide: ToastService, useValue: { error: () => {} } },
      ],
    });
  });
  it('retains inputs until the server accepts the background job', () => {
    const pending = new Subject<{ submission_id: string; status: string }>();
    service.submitAsync.and.returnValue(pending);
    const fixture = TestBed.createComponent(MultimodalComponent);
    const c = fixture.componentInstance;
    c.headline = 'বাংলা খবর';
    c.bodyText = 'খবরের সম্পূর্ণ লেখা এখানে দেওয়া হয়েছে';
    c.selectedFile = new File(['image'], 'news.png', { type: 'image/png' });
    c.onSubmit();
    fixture.detectChanges();
    expect(service.submitAsync).toHaveBeenCalledWith(c.headline, c.bodyText, c.selectedFile);
    expect(fixture.nativeElement.textContent).toContain(
      'You can leave after submission is accepted',
    );
    expect(fixture.nativeElement.querySelector('fieldset').disabled).toBeTrue();
    pending.next({ submission_id: 'm1', status: 'PENDING' });
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('You can continue browsing');
    expect(fixture.nativeElement.querySelector('a[href="/verify/m1"]')).not.toBeNull();
  });
  it('gives a finalized expert decision priority over the initial prediction', () => {
    const fixture = TestBed.createComponent(MultimodalComponent);
    fixture.componentInstance.result = RESULT;
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('.assessment-value').textContent.trim()).toBe(
      'Final decision: Real',
    );
    expect(fixture.nativeElement.textContent).toContain('EXPERT REVIEW COMPLETE');
    expect(fixture.nativeElement.querySelector('a[href="/verify/m1"]')).not.toBeNull();
  });
});
