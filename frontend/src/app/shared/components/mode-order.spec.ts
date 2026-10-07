import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { signal } from '@angular/core';
import { NavbarComponent } from './navbar/navbar.component';
import { FooterComponent } from './footer/footer.component';
import { AuthService } from '../../services/auth.service';
import { NotificationService } from '../../services/notification.service';
import { VerifyFactsComponent } from '../../features/verification/verify-facts/verify-facts';

/** Every place listing the three verification options uses the same order. */
const ORDER = [
  'News story against an image',
  'News story against claimed source',
  'Photocard against claimed source',
];

const texts = (root: HTMLElement, selector: string) =>
  Array.from(root.querySelectorAll<HTMLElement>(selector)).map((el) => el.textContent!.trim());

describe('verification option order', () => {
  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideRouter([]),
        {
          provide: AuthService,
          useValue: {
            isLoggedIn: signal(false),
            isAdmin: signal(false),
            isExpert: signal(false),
            user: signal(null),
            logout: () => undefined,
          },
        },
        { provide: NotificationService, useValue: { unreadCount: signal(0) } },
      ],
    });
  });

  it('navbar shows a single Verify facts link (desktop and mobile)', () => {
    const fixture = TestBed.createComponent(NavbarComponent);
    fixture.detectChanges();
    const el = fixture.nativeElement as HTMLElement;
    expect(texts(el, '.navbar-links a[href="/verify"]')).toEqual(['Verify facts']);
    fixture.componentInstance.mobileOpen = true;
    fixture.detectChanges();
    expect(texts(el, '.mobile-menu a[href="/verify"]')).toEqual(['Verify facts']);
  });

  it('footer', () => {
    const fixture = TestBed.createComponent(FooterComponent);
    fixture.detectChanges();
    expect(texts(fixture.nativeElement, 'nav[aria-label="Verify facts"] a')).toEqual(ORDER);
  });

  it('verify facts options', () => {
    const fixture = TestBed.createComponent(VerifyFactsComponent);
    fixture.detectChanges();
    expect(texts(fixture.nativeElement, '.option-title')).toEqual(ORDER);
  });
});
