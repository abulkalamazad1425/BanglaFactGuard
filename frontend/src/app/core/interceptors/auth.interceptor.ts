import { HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { catchError, switchMap, throwError } from 'rxjs';
import { StorageService } from '../../services/storage.service';
import { AuthService } from '../../services/auth.service';
import { environment } from '../../../environments/environment';

export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const storage = inject(StorageService);
  const auth = inject(AuthService);
  const isApi = req.url.startsWith(environment.apiUrl + '/');
  const publicAuth = /\/auth\/(login|register|refresh|logout|password-reset)(?:[/?-]|$)/.test(req.url);
  const token = isApi && !publicAuth ? storage.getAccessToken() : null;
  const owner = storage.getUser<{ id: string }>()?.id;
  const authorized = token ? req.clone({ setHeaders: { Authorization: `Bearer ${token}` } }) : req;
  return next(authorized).pipe(catchError(err => {
    if (err.status !== 401 || !token || storage.getUser<{ id: string }>()?.id !== owner) return throwError(() => err);
    if (!storage.getRefreshToken()) { auth.expireSession(); return throwError(() => err); }
    return auth.refresh().pipe(switchMap(tokens => next(req.clone({ setHeaders: { Authorization: `Bearer ${tokens.access_token}` } })).pipe(
      catchError(retryError => {
        if (retryError.status === 401 && storage.getAccessToken() === tokens.access_token) auth.expireSession();
        return throwError(() => retryError);
      }),
    )));
  }));
};
