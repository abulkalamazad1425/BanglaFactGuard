import { Injectable, computed, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { Observable, tap, catchError, throwError } from 'rxjs';
import { API_ENDPOINTS } from '../constants/api-endpoints.constant';
import { LoginRequest, RegisterRequest, TokenResponse, User } from '../models/user.model';
import { ApiService } from './api.service';
import { StorageService } from './storage.service';

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly api = inject(ApiService);
  private readonly storage = inject(StorageService);
  private readonly router = inject(Router);

  // ── Reactive Auth State ─────────────────────────────────────
  private readonly _user = signal<User | null>(this.storage.getUser<User>());

  readonly user = this._user.asReadonly();
  readonly isLoggedIn = computed(() => this._user() !== null);
  readonly isAdmin = computed(() => this._user()?.role === 'admin');
  readonly isExpert = computed(() => this._user()?.role === 'expert' || this._user()?.role === 'admin');

  // ── Registration ────────────────────────────────────────────
  register(req: RegisterRequest): Observable<User> {
    return this.api.post<User>(API_ENDPOINTS.AUTH_REGISTER, req).pipe(
      tap(user => this._handleAuthSuccess(user))
    );
  }

  // ── Login ────────────────────────────────────────────────────
  login(req: LoginRequest): Observable<TokenResponse> {
    return this.api.post<TokenResponse>(API_ENDPOINTS.AUTH_LOGIN, req).pipe(
      tap(tokens => {
        this.storage.setTokens(tokens.access_token, tokens.refresh_token);
        this._loadMe();
      })
    );
  }

  // ── Refresh ─────────────────────────────────────────────────
  refresh(): Observable<TokenResponse> {
    const refreshToken = this.storage.getRefreshToken();
    return this.api.post<TokenResponse>(API_ENDPOINTS.AUTH_REFRESH, {
      refresh_token: refreshToken,
    }).pipe(
      tap(tokens => {
        this.storage.setTokens(tokens.access_token, tokens.refresh_token);
      }),
      catchError(err => {
        this.logout();
        return throwError(() => err);
      })
    );
  }

  // ── Logout ──────────────────────────────────────────────────
  logout(): void {
    const refreshToken = this.storage.getRefreshToken();
    if (refreshToken) {
      this.api.post(API_ENDPOINTS.AUTH_LOGOUT, { refresh_token: refreshToken })
        .subscribe({ error: () => {} }); // fire and forget
    }
    this.storage.clearTokens();
    this._user.set(null);
    this.router.navigate(['/auth/login']);
  }

  // ── Load current user ────────────────────────────────────────
  loadCurrentUser(): Observable<User> {
    return this.api.get<User>(API_ENDPOINTS.AUTH_ME).pipe(
      tap(user => {
        this._user.set(user);
        this.storage.setUser(user);
      }),
      catchError(err => {
        this._user.set(null);
        return throwError(() => err);
      })
    );
  }

  // ── Change password ─────────────────────────────────────────
  changePassword(current_password: string, new_password: string): Observable<{ message: string }> {
    return this.api.post<{ message: string }>(API_ENDPOINTS.AUTH_CHANGE_PASSWORD, {
      current_password,
      new_password,
    });
  }

  // ── Password reset ───────────────────────────────────────────
  requestPasswordReset(email: string): Observable<{ message: string }> {
    return this.api.post<{ message: string }>(API_ENDPOINTS.AUTH_PASSWORD_RESET_REQUEST, { email });
  }

  confirmPasswordReset(token: string, new_password: string): Observable<{ message: string }> {
    return this.api.post<{ message: string }>(API_ENDPOINTS.AUTH_PASSWORD_RESET_CONFIRM, {
      token,
      new_password,
    });
  }

  // ── Internal ─────────────────────────────────────────────────
  private _handleAuthSuccess(user: User): void {
    if (user.access_token) {
      this.storage.setTokens(user.access_token, user.refresh_token ?? '');
    }
    // Strip tokens from user object before storing
    const { access_token, refresh_token, token_type, expires_in, ...cleanUser } = user;
    this._user.set(cleanUser as User);
    this.storage.setUser(cleanUser);
  }

  private _loadMe(): void {
    this.loadCurrentUser().subscribe({ error: () => {} });
  }
}
