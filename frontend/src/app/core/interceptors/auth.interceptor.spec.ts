import { TestBed } from '@angular/core/testing';
import { HttpClient, provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { Router } from '@angular/router';
import { authInterceptor } from './auth.interceptor';
import { StorageService } from '../../services/storage.service';
import { environment } from '../../../environments/environment';
import { AuthService } from '../../services/auth.service';

describe('Session refresh', () => {
  let http: HttpClient;
  let control: HttpTestingController;
  let storage: StorageService;
  let router: jasmine.SpyObj<Router>;
  const url = environment.apiUrl;
  const settle = () => new Promise((resolve) => setTimeout(resolve, 0));
  beforeEach(() => {
    router = jasmine.createSpyObj('Router', ['navigate']);
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptors([authInterceptor])),
        provideHttpClientTesting(),
        { provide: Router, useValue: router },
      ],
    });
    http = TestBed.inject(HttpClient);
    control = TestBed.inject(HttpTestingController);
    storage = TestBed.inject(StorageService);
    storage.clearTokens();
    storage.setTokens('old-access', 'old-refresh');
    if (navigator.locks)
      spyOn(navigator.locks, 'request').and.callFake(((name: string, callback: () => unknown) =>
        callback()) as typeof navigator.locks.request);
  });
  afterEach(() => {
    control.verify();
    storage.clearTokens();
  });

  it('shares one refresh for simultaneous 401s and retries with rotated credentials', async () => {
    let completed = 0;
    http.get(url + '/users/me/profile').subscribe(() => completed++);
    http.get(url + '/notifications/count').subscribe(() => completed++);
    control.expectOne(url + '/users/me/profile').flush({}, { status: 401, statusText: 'Expired' });
    control
      .expectOne(url + '/notifications/count')
      .flush({}, { status: 401, statusText: 'Expired' });
    const refresh = control.expectOne(url + '/auth/refresh');
    expect(refresh.request.body.refresh_token).toBe('old-refresh');
    refresh.flush({
      access_token: 'new-access',
      refresh_token: 'new-refresh',
      token_type: 'bearer',
      expires_in: 900,
    });
    await settle();
    const retries = control.match((r) => !r.url.endsWith('/auth/refresh'));
    expect(retries.length).toBe(2);
    for (const retry of retries) {
      expect(retry.request.headers.get('Authorization')).toBe('Bearer new-access');
      retry.flush({});
    }
    expect(completed).toBe(2);
    expect(storage.getRefreshToken()).toBe('new-refresh');
    expect(router.navigate).not.toHaveBeenCalled();
  });

  it('preserves the session on a temporary refresh failure', async () => {
    http.get(url + '/users/me/profile').subscribe({ error: () => {} });
    control.expectOne(url + '/users/me/profile').flush({}, { status: 401, statusText: 'Expired' });
    control.expectOne(url + '/auth/refresh').flush({}, { status: 503, statusText: 'Unavailable' });
    await settle();
    expect(storage.getRefreshToken()).toBe('old-refresh');
    expect(router.navigate).not.toHaveBeenCalled();
  });

  it('requires sign-in only when refresh credentials are rejected', async () => {
    http.get(url + '/users/me/profile').subscribe({ error: () => {} });
    control.expectOne(url + '/users/me/profile').flush({}, { status: 401, statusText: 'Expired' });
    control.expectOne(url + '/auth/refresh').flush({}, { status: 401, statusText: 'Expired' });
    await settle();
    expect(storage.getRefreshToken()).toBeNull();
    expect(router.navigate).toHaveBeenCalled();
  });

  it('does not attach credentials to unrelated hosts or refresh failed logins', () => {
    http.get('https://example.org/data').subscribe({ error: () => {} });
    const other = control.expectOne('https://example.org/data');
    expect(other.request.headers.has('Authorization')).toBeFalse();
    other.flush({}, { status: 401, statusText: 'Unauthorized' });
    http.post(url + '/auth/login', {}).subscribe({ error: () => {} });
    control.expectOne(url + '/auth/login').flush({}, { status: 401, statusText: 'Invalid' });
    control.expectNone(url + '/auth/refresh');
  });
});

describe('Proactive session refresh', () => {
  let control: HttpTestingController;
  let storage: StorageService;
  let router: jasmine.SpyObj<Router>;
  const url = environment.apiUrl;
  const jwt = (expSecondsFromNow: number) =>
    'h.' + btoa(JSON.stringify({ exp: Math.floor(Date.now() / 1000) + expSecondsFromNow })) + '.s';

  beforeEach(() => {
    router = jasmine.createSpyObj('Router', ['navigate']);
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptors([authInterceptor])),
        provideHttpClientTesting(),
        { provide: Router, useValue: router },
      ],
    });
    control = TestBed.inject(HttpTestingController);
    storage = TestBed.inject(StorageService);
    storage.clearTokens();
    if (navigator.locks)
      spyOn(navigator.locks, 'request').and.callFake(((name: string, callback: () => unknown) =>
        callback()) as typeof navigator.locks.request);
  });
  afterEach(() => {
    storage.clearTokens();
  });

  it('renews the access token before it expires, without waiting for a 401', async () => {
    storage.setTokens(jwt(30), 'refresh-1'); // expires within the one-minute lead
    const auth = TestBed.inject(AuthService);
    auth.refreshIfExpiringSoon();
    const refresh = control.expectOne(url + '/auth/refresh');
    expect(refresh.request.body.refresh_token).toBe('refresh-1');
    refresh.flush({
      access_token: jwt(900),
      refresh_token: 'refresh-2',
      token_type: 'bearer',
      expires_in: 900,
    });
    await new Promise((r) => setTimeout(r, 0));
    expect(storage.getRefreshToken()).toBe('refresh-2');
    expect(router.navigate).not.toHaveBeenCalled();
  });

  it('does not refresh a token that is still fresh', () => {
    storage.setTokens(jwt(900), 'refresh-1');
    TestBed.inject(AuthService).refreshIfExpiringSoon();
    control.expectNone(url + '/auth/refresh');
  });

  it('keeps the user signed in when a proactive refresh fails temporarily', async () => {
    storage.setTokens(jwt(10), 'refresh-1');
    TestBed.inject(AuthService).refreshIfExpiringSoon();
    control.expectOne(url + '/auth/refresh').flush({}, { status: 0, statusText: 'Network' });
    await new Promise((r) => setTimeout(r, 0));
    expect(storage.getRefreshToken()).toBe('refresh-1');
    expect(router.navigate).not.toHaveBeenCalled();
  });
});
