import { TestBed, fakeAsync, tick, discardPeriodicTasks } from '@angular/core/testing';
import { Subject, throwError } from 'rxjs';
import { PendingVerificationsService, isDeletedOnServer } from './pending-verifications.service';
import { VerificationService } from './verification.service';
import { ToastService } from '../shared/services/toast.service';

describe('PendingVerificationsService', () => {
  beforeEach(() => localStorage.removeItem('bfg.pending_verifications'));

  it('recognises only the API naming this submission as not found', () => {
    expect(isDeletedOnServer({ status: 404, error: { detail: { error: 'not_found', submission_id: 'a' } } }, 'a')).toBeTrue();
    expect(isDeletedOnServer({ status: 404, error: { detail: 'Not Found' } }, 'a')).toBeFalse();
    expect(isDeletedOnServer({ status: 404, error: { detail: { error: 'not_found', submission_id: 'b' } } }, 'a')).toBeFalse();
    expect(isDeletedOnServer({ status: 0 }, 'a')).toBeFalse();
  });

  it('forgets a tracked submission that was deleted on the server', fakeAsync(() => {
    const status = jasmine.createSpy('getStatus');
    const toast = jasmine.createSpyObj('ToastService', ['success', 'error']);
    TestBed.configureTestingModule({
      providers: [
        { provide: VerificationService, useValue: { getStatus: status } },
        { provide: ToastService, useValue: toast },
      ],
    });
    const svc = TestBed.inject(PendingVerificationsService);
    status.and.returnValue(new Subject()); // first ticks: no answer yet
    svc.track('gone', 'A claim', 'prothomalo.com');
    svc.track('kept', 'Another claim', 'prothomalo.com');
    status.and.callFake((id: string) => throwError(() => id === 'gone'
      ? { status: 404, error: { detail: { error: 'not_found', submission_id: 'gone' } } }
      : { status: 503, error: {} }));
    tick(4000);
    expect(svc.all().map((i) => i.submissionId)).toEqual(['kept']);
    expect(toast.success).not.toHaveBeenCalled();
    expect(toast.error).not.toHaveBeenCalled();
    expect(localStorage.getItem('bfg.pending_verifications')).not.toContain('gone');
    discardPeriodicTasks();
  }));
});
