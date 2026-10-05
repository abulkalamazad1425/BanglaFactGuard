import { TestBed } from '@angular/core/testing';
import { HttpClient, provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { Router } from '@angular/router';
import { authInterceptor } from './auth.interceptor';
import { StorageService } from '../../services/storage.service';
import { environment } from '../../../environments/environment';

describe('Session refresh', () => {
  let http: HttpClient;
  let control: HttpTestingController;
  let storage: StorageService;
  let router: jasmine.SpyObj<Router>;
  const url = environment.apiUrl;
  const settle = () => new Promise(resolve => setTimeout(resolve, 0));
  beforeEach(() => {
    router = jasmine.createSpyObj('Router', ['navigate']);
    TestBed.configureTestingModule({ providers: [provideHttpClient(withInterceptors([authInterceptor])), provideHttpClientTesting(), { provide: Router, useValue: router }] });
    http = TestBed.inject(HttpClient); control = TestBed.inject(HttpTestingController); storage = TestBed.inject(StorageService);
    storage.clearTokens(); storage.setTokens('old-access', 'old-refresh');
    if (navigator.locks) spyOn(navigator.locks, 'request').and.callFake(((name: string, callback: () => unknown) => callback()) as typeof navigator.locks.request);
  });
  afterEach(() => { control.verify(); storage.clearTokens(); });

  it('shares one refresh for simultaneous 401s and retries with rotated credentials', async () => {
    let completed = 0;
    http.get(url + '/users/me/profile').subscribe(() => completed++);
    http.get(url + '/notifications/count').subscribe(() => completed++);
    control.expectOne(url + '/users/me/profile').flush({}, { status: 401, statusText: 'Expired' });
    control.expectOne(url + '/notifications/count').flush({}, { status: 401, statusText: 'Expired' });
    const refresh = control.expectOne(url + '/auth/refresh');
    expect(refresh.request.body.refresh_token).toBe('old-refresh');
    refresh.flush({ access_token: 'new-access', refresh_token: 'new-refresh', token_type: 'bearer', expires_in: 900 });
    await settle();
    const retries = control.match(r => !r.url.endsWith('/auth/refresh'));
    expect(retries.length).toBe(2);
    for (const retry of retries) { expect(retry.request.headers.get('Authorization')).toBe('Bearer new-access'); retry.flush({}); }
    expect(completed).toBe(2); expect(storage.getRefreshToken()).toBe('new-refresh'); expect(router.navigate).not.toHaveBeenCalled();
  });

  it('preserves the session on a temporary refresh failure', async () => {
    http.get(url + '/users/me/profile').subscribe({ error: () => {} });
    control.expectOne(url + '/users/me/profile').flush({}, { status: 401, statusText: 'Expired' });
    control.expectOne(url + '/auth/refresh').flush({}, { status: 503, statusText: 'Unavailable' });
    await settle();
    expect(storage.getRefreshToken()).toBe('old-refresh'); expect(router.navigate).not.toHaveBeenCalled();
  });

  it('requires sign-in only when refresh credentials are rejected', async () => {
    http.get(url + '/users/me/profile').subscribe({ error: () => {} });
    control.expectOne(url + '/users/me/profile').flush({}, { status: 401, statusText: 'Expired' });
    control.expectOne(url + '/auth/refresh').flush({}, { status: 401, statusText: 'Expired' });
    await settle();
    expect(storage.getRefreshToken()).toBeNull(); expect(router.navigate).toHaveBeenCalled();
  });

  it('does not attach credentials to unrelated hosts or refresh failed logins', () => {
    http.get('https://example.org/data').subscribe({ error: () => {} });
    const other = control.expectOne('https://example.org/data'); expect(other.request.headers.has('Authorization')).toBeFalse(); other.flush({}, { status: 401, statusText: 'Unauthorized' });
    http.post(url + '/auth/login', {}).subscribe({ error: () => {} });
    control.expectOne(url + '/auth/login').flush({}, { status: 401, statusText: 'Invalid' });
    control.expectNone(url + '/auth/refresh');
  });
});
