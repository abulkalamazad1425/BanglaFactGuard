import { computed, signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { NavbarComponent } from './navbar.component';
import { AuthService } from '../../../services/auth.service';
import { NotificationService } from '../../../services/notification.service';

type Role = 'user' | 'expert' | 'admin' | null;

function desktopLinks(role: Role): string[] {
  const user = signal(role ? { role, full_name: 'Test', email: 't@example.com' } : null);
  TestBed.configureTestingModule({
    providers: [
      provideRouter([]),
      {
        provide: AuthService,
        useValue: {
          user,
          isLoggedIn: computed(() => user() !== null),
          isAdmin: computed(() => user()?.role === 'admin'),
          isExpert: computed(() => user()?.role === 'expert' || user()?.role === 'admin'),
          logout: () => {},
        },
      },
      { provide: NotificationService, useValue: { unreadCount: signal(0) } },
    ],
  });
  const fixture = TestBed.createComponent(NavbarComponent);
  fixture.detectChanges();
  const links = fixture.nativeElement.querySelectorAll('.navbar-links a');
  return Array.from(links as NodeListOf<HTMLElement>).map((a) => a.textContent!.trim());
}

describe('NavbarComponent links by role', () => {
  const base = ['Home', 'Verify facts', 'Fact Explorer'];

  it('shows only the public links to visitors', () => {
    expect(desktopLinks(null)).toEqual(base);
  });

  it('adds My Submissions and About for registered users', () => {
    expect(desktopLinks('user')).toEqual([...base, 'My Submissions', 'About']);
  });

  it('adds Expert Queue and Review History for expert reviewers', () => {
    expect(desktopLinks('expert')).toEqual([...base, 'Expert Queue', 'Review History']);
  });

  it('keeps the admin links and labels the admin panel "Administration"', () => {
    expect(desktopLinks('admin')).toEqual([...base, 'Review queue', 'Administration']);
  });
});
