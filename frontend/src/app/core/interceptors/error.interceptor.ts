import { HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { catchError, throwError } from 'rxjs';
import { ToastService } from '../../shared/services/toast.service';

export const errorInterceptor: HttpInterceptorFn = (req, next) => {
  const toast = inject(ToastService);

  return next(req).pipe(
    catchError(err => {
      const status = err.status;

      if (status === 401) {
        // Authentication handles refresh and session invalidation.
      } else if (status === 403) {
        toast.error('You do not have permission to perform this action.');
      } else if (status === 422) {
        // Validation errors — let components handle them
      } else if (status >= 500) {
        toast.error('This service is temporarily unavailable. Please try again shortly.');
      } else if (status === 0) {
        toast.error('Unable to connect. Check your connection and try again.');
      }

      return throwError(() => err);
    })
  );
};
