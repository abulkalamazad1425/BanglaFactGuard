import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { of, throwError } from 'rxjs';
import { PhotoCardComponent } from './photocard';
import { PhotoCardService } from '../../services/photocard.service';
import { PendingVerificationsService } from '../../services/pending-verifications.service';
import { SourceService } from '../../services/source.service';
import { ToastService } from '../../shared/services/toast.service';
import { PhotoCardAccepted } from '../../models/photocard.model';

const ACCEPTED: PhotoCardAccepted = {
  submission_id: 'sub-123',
  status: 'PENDING',
  phase: 'QUEUED',
  message: 'Your card was received. You can leave this page.',
  queued_at: '2026-06-07T10:00:00Z',
};

describe('PhotoCardComponent (background submission)', () => {
  let svc: jasmine.SpyObj<PhotoCardService>;
  let pending: jasmine.SpyObj<PendingVerificationsService>;
  let toast: jasmine.SpyObj<ToastService>;

  function setup() {
    svc = jasmine.createSpyObj('PhotoCardService', ['submitAsync', 'getResult']);
    pending = jasmine.createSpyObj('PendingVerificationsService', ['track']);
    toast = jasmine.createSpyObj('ToastService', ['error', 'success']);
    TestBed.configureTestingModule({
      imports: [PhotoCardComponent],
      providers: [
        provideRouter([]),
        { provide: PhotoCardService, useValue: svc },
        { provide: PendingVerificationsService, useValue: pending },
        { provide: ToastService, useValue: toast },
        { provide: SourceService, useValue: { listSources: () => of({ items: [] }) } },
      ],
    });
    const fixture = TestBed.createComponent(PhotoCardComponent);
    fixture.detectChanges();
    const cmp = fixture.componentInstance;
    cmp.selectedFile = new File(['x'], 'card.png', { type: 'image/png' });
    return { fixture, cmp };
  }

  it('submits only the image through the 202 background endpoint', () => {
    const { cmp, fixture } = setup();
    svc.submitAsync.and.returnValue(of(ACCEPTED));
    const el = fixture.nativeElement as HTMLElement;
    // no outlet, date or "check again" inputs: they are read from the card
    expect(el.querySelector('select')).toBeNull();
    expect(el.querySelector('input[type=date]')).toBeNull();
    expect(el.querySelector('input[type=checkbox]')).toBeNull();
    expect(el.textContent).not.toContain('updated evidence');
    cmp.verify();
    expect(svc.submitAsync).toHaveBeenCalledOnceWith({ image: cmp.selectedFile! });
  });

  it('lists the active verified outlets in a collapsed section', () => {
    TestBed.configureTestingModule({
      imports: [PhotoCardComponent],
      providers: [
        provideRouter([]),
        {
          provide: PhotoCardService,
          useValue: jasmine.createSpyObj('PhotoCardService', ['submitAsync']),
        },
        {
          provide: PendingVerificationsService,
          useValue: jasmine.createSpyObj('PendingVerificationsService', ['track']),
        },
        { provide: ToastService, useValue: jasmine.createSpyObj('ToastService', ['error']) },
        {
          provide: SourceService,
          useValue: {
            listSources: () =>
              of({
                items: [
                  {
                    canonical_name: 'jugantor.com',
                    display_name: 'যুগান্তর',
                    display_name_en: 'Jugantor',
                    is_active: true,
                  },
                  {
                    canonical_name: 'prothomalo.com',
                    display_name: 'প্রথম আলো',
                    display_name_en: 'Prothom Alo',
                    is_active: true,
                  },
                  { canonical_name: 'old.com', display_name: 'পুরনো', is_active: false },
                ],
              }),
          },
        },
      ],
    });
    const fixture = TestBed.createComponent(PhotoCardComponent);
    fixture.detectChanges();
    const details = (fixture.nativeElement as HTMLElement).querySelector(
      '.source-panel details',
    ) as HTMLDetailsElement;
    expect(details).not.toBeNull();
    expect(details.open).toBeFalse();
    expect(details.querySelector('summary')!.textContent).toContain('Show the 2 active outlets');
    const items = Array.from(details.querySelectorAll('li')).map((li) => li.textContent!.trim());
    expect(items.length).toBe(2);
    expect(items.join(' ')).toContain('Prothom Alo');
    expect(items.join(' ')).not.toContain('পুরনো');
  });

  it('after acceptance the user can leave: shows a received state with links and does not poll', () => {
    const { fixture, cmp } = setup();
    svc.submitAsync.and.returnValue(of(ACCEPTED));
    cmp.verify();
    fixture.detectChanges();

    expect(cmp.step).toBe('accepted');
    expect(cmp.verifying).toBeFalse();
    const text = (fixture.nativeElement as HTMLElement).textContent!;
    expect(text).toContain('was received');
    expect(text).toContain('My Submissions');
    const hrefs = Array.from((fixture.nativeElement as HTMLElement).querySelectorAll('a')).map(
      (a) => a.getAttribute('href'),
    );
    expect(hrefs).toContain('/verify/sub-123');
    // the page itself never polls for the result - the server job runs regardless
    expect(svc.getResult).not.toHaveBeenCalled();
    // the app-wide tracker is told so the user hears about it elsewhere in the app
    expect(pending.track).toHaveBeenCalledWith(
      'sub-123',
      'Photo card',
      jasmine.any(String),
      'PHOTO_CARD',
    );
  });

  it('rejects unsupported or oversized files before uploading', () => {
    const { cmp } = setup();
    cmp.onFileChange({
      target: { files: [new File(['x'], 'bad.svg', { type: 'image/svg+xml' })] },
    } as unknown as Event);
    expect(cmp.selectedFile).toBeNull();
    expect(cmp.errorMsg).toContain('supported');
    cmp.onFileChange({
      target: {
        files: [
          new File([new Uint8Array(10 * 1024 * 1024 + 1)], 'large.png', { type: 'image/png' }),
        ],
      },
    } as unknown as Event);
    expect(cmp.selectedFile).toBeNull();
    expect(cmp.errorMsg).toContain('10 MB');
    expect(svc.submitAsync).not.toHaveBeenCalled();
  });

  it('a failed upload stays on the form with an explanation', () => {
    const { cmp } = setup();
    svc.submitAsync.and.returnValue(
      throwError(() => ({
        error: { detail: { message: 'The image could not be stored right now.' } },
      })),
    );
    cmp.verify();
    expect(cmp.step).toBe('upload');
    expect(cmp.errorMsg).toContain('could not be submitted');
    expect(pending.track).not.toHaveBeenCalled();
  });
});
