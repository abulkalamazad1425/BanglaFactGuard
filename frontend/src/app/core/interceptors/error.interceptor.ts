import { HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { catchError, throwError } from 'rxjs';
import { AuthService } from '../services/auth.service';
import { ToastService } from '../../shared/services/toast.service';

export const errorInterceptor: HttpInterceptorFn = (req, next) => {
  const auth = inject(AuthService);
  const toast = inject(ToastService);

  return next(req).pipe(
    catchError(err => {
      const status = err.status;
      const message = err.error?.message || err.message || 'An error occurred';

      if (status === 401) {
        // Avoid logout loop on auth endpoints
        if (!req.url.includes('/auth/login') && !req.url.includes('/auth/register')) {
          auth.logout();
          toast.error('Session expired. Please log in again.');
        }
      } else if (status === 403) {
        toast.error('You do not have permission to perform this action.');
      } else if (status === 422) {
        // Validation errors — let components handle them
      } else if (status >= 500) {
        toast.error('Server error. Please try again later.');
      } else if (status === 0) {
        toast.error('Cannot connect to server. Is the backend running?');
      }

      return throwError(() => err);
    })
  );
};
