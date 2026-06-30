import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { AuthService } from '../services/auth.service';
import { UserRole } from '../models/user.model';

export const roleGuard = (...roles: UserRole[]): CanActivateFn => {
  return () => {
    const auth = inject(AuthService);
    const router = inject(Router);
    const user = auth.user();

    if (!user) {
      router.navigate(['/auth/login']);
      return false;
    }

    if (roles.includes(user.role)) {
      return true;
    }

    // Admin can access expert routes too
    if (roles.includes('expert') && user.role === 'admin') {
      return true;
    }

    router.navigate(['/']);
    return false;
  };
};
