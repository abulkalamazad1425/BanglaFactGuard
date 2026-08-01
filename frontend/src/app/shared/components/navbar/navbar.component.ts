import { Component, inject, computed } from '@angular/core';
import { RouterLink, RouterLinkActive } from '@angular/router';
import { CommonModule } from '@angular/common';
import { AuthService } from '../../../services/auth.service';
import { NotificationService } from '../../../services/notification.service';

@Component({
  selector: 'app-navbar',
  standalone: true,
  imports: [CommonModule, RouterLink, RouterLinkActive],
  template: `
    <nav class="navbar" [class.scrolled]="scrolled">
      <div class="navbar-container">
        <!-- Logo -->
        <a routerLink="/" class="navbar-brand">
          <div class="brand-icon">
            <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
              <path d="M14 2L24 7.5V20.5L14 26L4 20.5V7.5L14 2Z" fill="url(#grad)" opacity="0.9"/>
              <path d="M10 10.5L14 8L18 10.5V15.5L14 18L10 15.5V10.5Z" fill="white" opacity="0.9"/>
              <defs>
                <linearGradient id="grad" x1="4" y1="2" x2="24" y2="26" gradientUnits="userSpaceOnUse">
                  <stop stop-color="#5b3df0"/>
                  <stop offset="1" stop-color="#9333ea"/>
                </linearGradient>
              </defs>
            </svg>
          </div>
          <span class="brand-name">BanglaFactGuard</span>
        </a>

        <!-- Desktop Nav -->
        <div class="navbar-links">
          <a routerLink="/" routerLinkActive="active" [routerLinkActiveOptions]="{exact: true}" class="nav-link">Home</a>
          <a routerLink="/verify" routerLinkActive="active" class="nav-link">Verify Claim</a>
          <a routerLink="/multimodal" routerLinkActive="active" class="nav-link">Multimodal</a>
          <a routerLink="/dashboard" routerLinkActive="active" class="nav-link">Fact Explorer</a>
          @if (isExpert()) {
            <a routerLink="/expert/queue" routerLinkActive="active" class="nav-link nav-link--expert">Expert Queue</a>
          }
          @if (isAdmin()) {
            <a routerLink="/admin" routerLinkActive="active" class="nav-link nav-link--admin">Admin</a>
          }
        </div>

        <!-- Right Side -->
        <div class="navbar-actions">
          @if (isLoggedIn()) {
            <!-- Notifications -->
            <a routerLink="/notifications" class="notif-btn" [class.has-badge]="unreadCount() > 0">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/>
                <path d="M13.73 21a2 2 0 0 1-3.46 0"/>
              </svg>
              @if (unreadCount() > 0) {
                <span class="notif-badge">{{ unreadCount() > 9 ? '9+' : unreadCount() }}</span>
              }
            </a>

            <!-- User Menu -->
            <div class="user-menu" [class.open]="menuOpen">
              <button class="user-avatar" (click)="toggleMenu()">
                <div class="avatar-circle">{{ userInitial() }}</div>
                <span class="user-name">{{ userName() }}</span>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="chevron" [class.rotated]="menuOpen">
                  <polyline points="6 9 12 15 18 9"/>
                </svg>
              </button>
              @if (menuOpen) {
                <div class="dropdown-menu">
                  <a routerLink="/history" class="dropdown-item" (click)="closeMenu()">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
                    My Submissions
                  </a>
                  <a routerLink="/settings" class="dropdown-item" (click)="closeMenu()">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
                    Settings
                  </a>
                  <div class="dropdown-divider"></div>
                  <button class="dropdown-item dropdown-item--danger" (click)="logout()">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>
                    Logout
                  </button>
                </div>
              }
            </div>
          } @else {
            <a routerLink="/auth/login" class="btn btn-ghost btn-sm">Login</a>
            <a routerLink="/auth/register" class="btn btn-primary btn-sm">Get Started</a>
          }
        </div>

        <!-- Mobile toggle -->
        <button class="mobile-toggle" (click)="toggleMobileMenu()" [class.open]="mobileOpen">
          <span></span><span></span><span></span>
        </button>
      </div>

      <!-- Mobile Menu -->
      @if (mobileOpen) {
        <div class="mobile-menu animate-in">
          <a routerLink="/" class="mobile-link" (click)="closeMobileMenu()">Home</a>
          <a routerLink="/verify" class="mobile-link" (click)="closeMobileMenu()">Verify Claim</a>
          <a routerLink="/multimodal" class="mobile-link" (click)="closeMobileMenu()">Multimodal</a>
          <a routerLink="/dashboard" class="mobile-link" (click)="closeMobileMenu()">Fact Explorer</a>
          @if (isLoggedIn()) {
            <a routerLink="/history" class="mobile-link" (click)="closeMobileMenu()">My Submissions</a>
            <a routerLink="/notifications" class="mobile-link" (click)="closeMobileMenu()">Notifications</a>
            @if (isExpert()) {
              <a routerLink="/expert/queue" class="mobile-link" (click)="closeMobileMenu()">Expert Queue</a>
            }
            @if (isAdmin()) {
              <a routerLink="/admin" class="mobile-link" (click)="closeMobileMenu()">Admin Panel</a>
            }
            <button class="mobile-link mobile-link--danger" (click)="logout()">Logout</button>
          } @else {
            <a routerLink="/auth/login" class="mobile-link" (click)="closeMobileMenu()">Login</a>
            <a routerLink="/auth/register" class="mobile-link mobile-link--primary" (click)="closeMobileMenu()">Register</a>
          }
        </div>
      }
    </nav>
    <!-- Backdrop for dropdown -->
    @if (menuOpen) {
      <div class="backdrop" (click)="closeMenu()"></div>
    }
  `,
  styles: [`
    .navbar {
      position: fixed; top: 0; left: 0; right: 0; z-index: 1000;
      background: rgba(255,255,255,0.82);
      backdrop-filter: blur(20px);
      -webkit-backdrop-filter: blur(20px);
      border-bottom: 1px solid var(--border);
      transition: var(--transition);

      &.scrolled {
        background: rgba(255,255,255,0.95);
        box-shadow: var(--shadow-sm);
      }
    }

    .navbar-container {
      max-width: 1280px; margin: 0 auto;
      padding: 0 24px;
      height: 64px;
      display: flex; align-items: center; justify-content: space-between;
      gap: 24px;
    }

    .navbar-brand {
      display: flex; align-items: center; gap: 10px;
      text-decoration: none; color: var(--text-primary);
      flex-shrink: 0;
    }
    .brand-icon { display: flex; align-items: center; }
    .brand-name {
      font-family: var(--font-display); font-size: 18px; font-weight: 700;
      background: var(--gradient-primary);
      -webkit-background-clip: text; background-clip: text;
      -webkit-text-fill-color: transparent;
    }

    .navbar-links {
      display: flex; align-items: center; gap: 4px;
      @media (max-width: 768px) { display: none; }
    }

    .nav-link {
      padding: 6px 14px; border-radius: var(--radius-md);
      font-size: 14px; font-weight: 500; color: var(--text-secondary);
      text-decoration: none; transition: var(--transition);

      &:hover { color: var(--text-primary); background: var(--bg-surface-2); }
      &.active { color: var(--primary-light); background: rgba(124,106,247,0.1); }
      &--expert { color: var(--accent-light); }
      &--admin  { color: var(--warning); }
    }

    .navbar-actions {
      display: flex; align-items: center; gap: 12px;
      @media (max-width: 768px) { display: none; }
    }

    .notif-btn {
      position: relative; width: 38px; height: 38px;
      display: flex; align-items: center; justify-content: center;
      background: var(--bg-surface-2); border-radius: var(--radius-md);
      color: var(--text-secondary); text-decoration: none;
      transition: var(--transition); border: 1px solid var(--border);

      &:hover { color: var(--text-primary); border-color: var(--border-hover); }
    }
    .notif-badge {
      position: absolute; top: -4px; right: -4px;
      min-width: 18px; height: 18px; padding: 0 4px;
      background: var(--error); color: white;
      border-radius: var(--radius-full); font-size: 10px; font-weight: 700;
      display: flex; align-items: center; justify-content: center;
      border: 2px solid var(--bg-base);
    }

    .user-menu { position: relative; }
    .user-avatar {
      display: flex; align-items: center; gap: 8px;
      background: var(--bg-surface-2); border: 1px solid var(--border);
      border-radius: var(--radius-md); padding: 6px 12px;
      cursor: pointer; color: var(--text-primary);
      font-size: 14px; font-weight: 500; transition: var(--transition);

      &:hover { border-color: var(--primary); }
    }
    .avatar-circle {
      width: 28px; height: 28px; border-radius: 50%;
      background: var(--gradient-primary);
      display: flex; align-items: center; justify-content: center;
      font-size: 12px; font-weight: 700; color: white;
      flex-shrink: 0;
    }
    .user-name { max-width: 120px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .chevron { transition: transform 0.2s; &.rotated { transform: rotate(180deg); } }

    .dropdown-menu {
      position: absolute; top: calc(100% + 8px); right: 0;
      width: 200px; background: var(--bg-elevated);
      border: 1px solid var(--border); border-radius: var(--radius-md);
      box-shadow: var(--shadow-lg); overflow: hidden;
      animation: fadeIn 0.15s ease;
    }
    .dropdown-item {
      display: flex; align-items: center; gap: 10px;
      padding: 11px 16px; font-size: 14px; color: var(--text-secondary);
      text-decoration: none; background: none; border: none; width: 100%;
      cursor: pointer; transition: var(--transition); text-align: left;

      &:hover { background: var(--bg-surface-3); color: var(--text-primary); }
      &--danger { color: var(--error); &:hover { background: var(--error-bg); } }
    }
    .dropdown-divider { height: 1px; background: var(--border); margin: 4px 0; }

    .mobile-toggle {
      display: none; flex-direction: column; gap: 5px;
      background: none; border: none; cursor: pointer; padding: 8px;
      @media (max-width: 768px) { display: flex; }

      span {
        display: block; width: 22px; height: 2px;
        background: var(--text-secondary); border-radius: 2px;
        transition: var(--transition);
      }
      &.open span:nth-child(1) { transform: translateY(7px) rotate(45deg); }
      &.open span:nth-child(2) { opacity: 0; }
      &.open span:nth-child(3) { transform: translateY(-7px) rotate(-45deg); }
    }

    .mobile-menu {
      padding: 16px 24px 24px;
      border-top: 1px solid var(--border);
      background: var(--bg-surface);
      display: flex; flex-direction: column; gap: 4px;
    }
    .mobile-link {
      display: block; padding: 12px 16px; border-radius: var(--radius-md);
      font-size: 15px; color: var(--text-secondary);
      text-decoration: none; background: none; border: none;
      cursor: pointer; text-align: left; transition: var(--transition);

      &:hover { background: var(--bg-surface-2); color: var(--text-primary); }
      &--primary { background: rgba(124,106,247,0.1); color: var(--primary-light); }
      &--danger  { color: var(--error); }
    }

    .backdrop {
      position: fixed; inset: 0; z-index: 999;
    }
  `]
})
export class NavbarComponent {
  private readonly auth = inject(AuthService);
  private readonly notificationSvc = inject(NotificationService);

  scrolled = false;
  menuOpen = false;
  mobileOpen = false;

  readonly isLoggedIn = this.auth.isLoggedIn;
  readonly isAdmin = this.auth.isAdmin;
  readonly isExpert = this.auth.isExpert;
  readonly unreadCount = this.notificationSvc.unreadCount;

  readonly userName = computed(() => {
    const u = this.auth.user();
    return u?.full_name || u?.email?.split('@')[0] || 'User';
  });

  readonly userInitial = computed(() => {
    const name = this.userName();
    return name.charAt(0).toUpperCase();
  });

  toggleMenu(): void { this.menuOpen = !this.menuOpen; }
  closeMenu(): void { this.menuOpen = false; }
  toggleMobileMenu(): void { this.mobileOpen = !this.mobileOpen; }
  closeMobileMenu(): void { this.mobileOpen = false; }

  logout(): void {
    this.closeMenu();
    this.closeMobileMenu();
    this.auth.logout();
  }
}
