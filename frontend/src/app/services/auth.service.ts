import { Injectable, computed, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { Observable, tap, catchError, throwError, defer, finalize, shareReplay, firstValueFrom, timeout } from 'rxjs';
import { HttpBackend, HttpClient, HttpErrorResponse } from '@angular/common/http';
import { environment } from '../../environments/environment';
import { API_ENDPOINTS } from '../core/constants/api-endpoints.constant';
import { LoginRequest, RegisterRequest, TokenResponse, User, UserProfile, UpdateProfileRequest } from '../models/user.model';
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

  // ── Proactive refresh ───────────────────────────────────────
  // The access token is short-lived. It is renewed shortly BEFORE it expires
  // (and whenever the tab wakes, regains focus or comes back online), so
  // requests do not fail with 401 first. The session ends only on logout or
  // when the server rejects the refresh token itself.
  private static readonly REFRESH_LEAD_MS = 60_000;
  private static readonly RETRY_MS = 30_000;
  private refreshTimer?: ReturnType<typeof setTimeout>;

  constructor() {
    this.scheduleRefresh();
    if (typeof window !== 'undefined' && typeof document !== 'undefined') {
      const wake = () => { if (document.visibilityState !== 'hidden') this.refreshIfExpiringSoon(); };
      document.addEventListener('visibilitychange', wake);
      window.addEventListener('focus', wake);
      window.addEventListener('online', wake);
      // Another tab rotated the shared tokens: follow its schedule.
      window.addEventListener('storage', e => { if (e.key === null || e.key === 'bfg_access_token') this.scheduleRefresh(); });
    }
  }

  /** Access-token expiry (ms since epoch) from its JWT `exp`, or null. */
  private accessExpiry(): number | null {
    const token = this.storage.getAccessToken();
    const payload = token?.split('.')[1];
    if (!payload) return null;
    try {
      const json = JSON.parse(atob(payload.replace(/-/g, '+').replace(/_/g, '/')));
      return typeof json.exp === 'number' ? json.exp * 1000 : null;
    } catch {
      return null;
    }
  }

  private scheduleRefresh(delayMs?: number): void {
    clearTimeout(this.refreshTimer);
    this.refreshTimer = undefined;
    if (!this.storage.getRefreshToken()) return;
    const expiry = this.accessExpiry();
    if (delayMs === undefined) {
      if (expiry === null) return;
      delayMs = expiry - Date.now() - AuthService.REFRESH_LEAD_MS;
    }
    this.refreshTimer = setTimeout(() => this.refreshIfExpiringSoon(), Math.min(Math.max(delayMs, 0), 2_147_000_000));
  }

  /** Refresh now if the access token expires within the lead time. */
  refreshIfExpiringSoon(): void {
    if (!this.storage.getRefreshToken()) return;
    const expiry = this.accessExpiry();
    if (expiry === null) return; // undecodable: the 401 path still refreshes
    if (expiry - Date.now() > AuthService.REFRESH_LEAD_MS) { this.scheduleRefresh(); return; }
    this.refresh().subscribe({
      // A network/server failure is not a logout: keep the session and retry.
      error: err => { if (err?.status !== 401 && err?.status !== 403) this.scheduleRefresh(AuthService.RETRY_MS); },
    });
  }

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
        this.scheduleRefresh();
        this._loadMe();
      })
    );
  }

  private readonly rawHttp = new HttpClient(inject(HttpBackend));
  private refreshRequest?: Observable<TokenResponse>;

  expireSession(): void {
    clearTimeout(this.refreshTimer);
    this.storage.clearTokens();
    this._user.set(null);
    void this.router.navigate(['/auth/login']);
  }

  // ── Refresh ─────────────────────────────────────────────────
  refresh(): Observable<TokenResponse> {
    if (this.refreshRequest) return this.refreshRequest;
    const originalToken = this.storage.getRefreshToken();
    const originalOwner = this.storage.getUser<User>()?.id;
    const exchange = async (): Promise<TokenResponse> => {
      const currentToken = this.storage.getRefreshToken();
      if (this.storage.getUser<User>()?.id !== originalOwner) throw new HttpErrorResponse({ status: 401 });
      // Another tab may have rotated the shared refresh token while we waited.
      if (currentToken && currentToken !== originalToken) {
        return { access_token: this.storage.getAccessToken()!, refresh_token: currentToken, token_type: 'bearer', expires_in: 0 };
      }
      if (!currentToken) throw new HttpErrorResponse({ status: 401 });
      const tokens = await firstValueFrom(this.rawHttp.post<TokenResponse>(environment.apiUrl + API_ENDPOINTS.AUTH_REFRESH, { refresh_token: currentToken }).pipe(timeout(15000)));
      // An explicit logout during refresh must not restore the session.
      if (this.storage.getRefreshToken() !== currentToken) throw new HttpErrorResponse({ status: 401 });
      this.storage.setTokens(tokens.access_token, tokens.refresh_token);
      this.scheduleRefresh();
      return tokens;
    };
    this.refreshRequest = defer(() => typeof navigator !== 'undefined' && navigator.locks
      ? navigator.locks.request('banglafactguard-refresh', exchange) : exchange()).pipe(
      catchError(err => {
        if ((err.status === 401 || err.status === 403) && this.storage.getRefreshToken() === originalToken) this.expireSession();
        return throwError(() => err);
      }),
      finalize(() => { this.refreshRequest = undefined; }),
      shareReplay({ bufferSize: 1, refCount: false }),
    );
    return this.refreshRequest;
  }

  // ── Logout ──────────────────────────────────────────────────
  logout(): void {
    const refreshToken = this.storage.getRefreshToken();
    if (refreshToken) {
      this.api.post(API_ENDPOINTS.AUTH_LOGOUT, { refresh_token: refreshToken })
        .subscribe({ error: () => { } }); // fire and forget
    }
    clearTimeout(this.refreshTimer);
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
        return throwError(() => err);
      })
    );
  }

  // ── Profile ─────────────────────────────────────────────────
  getProfile(): Observable<UserProfile> {
    return this.api.get<UserProfile>(API_ENDPOINTS.USERS_PROFILE);
  }

  updateProfile(data: UpdateProfileRequest): Observable<UserProfile> {
    return this.api.put<UserProfile>(API_ENDPOINTS.USERS_PROFILE, data).pipe(
      tap(() => this._loadMe()) // Reload user to reflect changes (e.g. full_name)
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

  confirmPasswordReset(email: string, otp: string, new_password: string): Observable<{ message: string }> {
    return this.api.post<{ message: string }>(API_ENDPOINTS.AUTH_PASSWORD_RESET_CONFIRM, {
      email,
      otp,
      new_password,
    });
  }

  // ── Internal ─────────────────────────────────────────────────
  private _handleAuthSuccess(user: User): void {
    if (user.access_token) {
      this.storage.setTokens(user.access_token, user.refresh_token ?? '');
      this.scheduleRefresh();
    }
    // Strip tokens from user object before storing
    const { access_token, refresh_token, token_type, expires_in, ...cleanUser } = user;
    this._user.set(cleanUser as User);
    this.storage.setUser(cleanUser);
  }

  private _loadMe(): void {
    this.loadCurrentUser().subscribe({ error: () => { } });
  }
}
