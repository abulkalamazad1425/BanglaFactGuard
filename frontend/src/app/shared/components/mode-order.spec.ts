import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { signal } from '@angular/core';
import { of } from 'rxjs';
import { NavbarComponent } from './navbar/navbar.component';
import { FooterComponent } from './footer/footer.component';
import { AuthService } from '../../services/auth.service';
import { NotificationService } from '../../services/notification.service';
import { PhotoCardComponent } from '../../features/photocard/photocard';
import { PhotoCardService } from '../../services/photocard.service';
import { PendingVerificationsService } from '../../services/pending-verifications.service';
import { SourceService } from '../../services/source.service';
import { ToastService } from '../services/toast.service';

/** Every place listing the three input modes uses the same order. */
const ORDER = ['Text & source', 'Photo card', 'Text & image'];
const MODE_ROUTES: Record<string, string> = { '/verify': ORDER[0], '/photo-card': ORDER[1], '/multimodal': ORDER[2] };

function modeLabels(root: HTMLElement, selector = 'a'): string[] {
  return Array.from(root.querySelectorAll<HTMLAnchorElement>(selector))
    .filter((a) => MODE_ROUTES[a.getAttribute('href') ?? ''])
    .map((a) => a.textContent!.trim());
}

describe('input mode order', () => {
  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideRouter([]),
        { provide: AuthService, useValue: { isLoggedIn: signal(false), isAdmin: signal(false), isExpert: signal(false), user: signal(null), logout: () => undefined } },
        { provide: NotificationService, useValue: { unreadCount: signal(0) } },
        { provide: PhotoCardService, useValue: {} },
        { provide: PendingVerificationsService, useValue: {} },
        { provide: ToastService, useValue: {} },
        { provide: SourceService, useValue: { listSources: () => of({ items: [] }) } },
      ],
    });
  });

  it('navbar (desktop and mobile)', () => {
    const fixture = TestBed.createComponent(NavbarComponent);
    fixture.detectChanges();
    const el = fixture.nativeElement as HTMLElement;
    expect(modeLabels(el, '.navbar-links a')).toEqual(ORDER);
    fixture.componentInstance.mobileOpen = true;
    fixture.detectChanges();
    expect(modeLabels(el, '.mobile-menu a')).toEqual(ORDER);
  });

  it('footer', () => {
    const fixture = TestBed.createComponent(FooterComponent);
    fixture.detectChanges();
    expect(modeLabels(fixture.nativeElement)).toEqual(ORDER);
  });

  it('method tabs on the input pages', () => {
    const fixture = TestBed.createComponent(PhotoCardComponent);
    fixture.detectChanges();
    expect(modeLabels(fixture.nativeElement, '.method-nav a')).toEqual(ORDER);
  });
});
