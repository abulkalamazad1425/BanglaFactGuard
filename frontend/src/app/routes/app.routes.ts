import { Routes } from '@angular/router';
import { MainLayoutComponent } from '../layouts/main-layout/main-layout.component';
import { AuthLayoutComponent } from '../layouts/auth-layout/auth-layout.component';
import { authGuard } from '../core/guards/auth.guard';
import { roleGuard } from '../core/guards/role.guard';

export const APP_ROUTES: Routes = [
  // ── Auth Layout ──────────────────────────────────────────────
  {
    path: 'auth',
    component: AuthLayoutComponent,
    children: [
      { path: 'login',          loadComponent: () => import('../features/auth/login/login').then(m => m.LoginComponent) },
      { path: 'register',       loadComponent: () => import('../features/auth/register/register').then(m => m.RegisterComponent) },
      { path: 'forgot-password',loadComponent: () => import('../features/auth/forgot-password/forgot-password').then(m => m.ForgotPasswordComponent) },
      { path: '', redirectTo: 'login', pathMatch: 'full' },
    ],
  },

  // ── Main Layout ──────────────────────────────────────────────
  {
    path: '',
    component: MainLayoutComponent,
    children: [
      // Public
      { path: '',          loadComponent: () => import('../features/home/home').then(m => m.HomeComponent) },
      { path: 'dashboard', loadComponent: () => import('../features/dashboard/public-dashboard/public-dashboard').then(m => m.PublicDashboardComponent) },
      { path: 'verify',    loadComponent: () => import('../features/verification/verify-claim/verify-claim').then(m => m.VerifyClaimComponent) },
      { path: 'verify/:id',loadComponent: () => import('../features/verification/verify-result/verify-result').then(m => m.VerifyResultComponent) },
      { path: 'multimodal',loadComponent: () => import('../features/multimodal/multimodal').then(m => m.MultimodalComponent) },

      // Authenticated
      {
        path: 'history',
        canActivate: [authGuard],
        loadComponent: () => import('../features/history/submission-history/submission-history').then(m => m.SubmissionHistoryComponent),
      },
      {
        path: 'notifications',
        canActivate: [authGuard],
        loadComponent: () => import('../features/notifications/notification-list/notification-list').then(m => m.NotificationListComponent),
      },
      {
        path: 'settings',
        canActivate: [authGuard],
        loadComponent: () => import('../features/settings/profile-settings/profile-settings').then(m => m.ProfileSettingsComponent),
      },

      // Expert
      {
        path: 'expert',
        canActivate: [authGuard, roleGuard('expert')],
        children: [
          { path: '',        redirectTo: 'queue', pathMatch: 'full' },
          { path: 'queue',   loadComponent: () => import('../features/expert/expert-queue/expert-queue').then(m => m.ExpertQueueComponent) },
          { path: 'queue/:id', loadComponent: () => import('../features/expert/expert-review-detail/expert-review-detail').then(m => m.ExpertReviewDetailComponent) },
          { path: 'history', loadComponent: () => import('../features/expert/expert-history/expert-history').then(m => m.ExpertHistoryComponent) },
          { path: 'stats',   loadComponent: () => import('../features/expert/expert-stats/expert-stats').then(m => m.ExpertStatsComponent) },
        ],
      },

      // Admin
      {
        path: 'admin',
        canActivate: [authGuard, roleGuard('admin')],
        children: [
          { path: '',            loadComponent: () => import('../features/admin/admin-dashboard/admin-dashboard').then(m => m.AdminDashboardComponent) },
          { path: 'experts',     loadComponent: () => import('../features/admin/expert-management/expert-management').then(m => m.ExpertManagementComponent) },
          { path: 'experts/new', loadComponent: () => import('../features/admin/create-expert/create-expert').then(m => m.CreateExpertComponent) },
          { path: 'sources',     loadComponent: () => import('../features/admin/source-management/source-management.component').then(m => m.SourceManagementComponent) },
          { path: 'credibility-tiers', loadComponent: () => import('../features/admin/credibility-tiers/credibility-tiers').then(m => m.CredibilityTiersComponent) },
        ],
      },

      // 404
      { path: '**', loadComponent: () => import('../features/not-found/not-found').then(m => m.NotFoundComponent) },
    ],
  },
];
